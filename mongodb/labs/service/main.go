// Original teaching service. Data remains in the separately managed mongod.
package main

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"sort"
	"strings"
	"sync/atomic"
	"syscall"
	"time"

	"go.mongodb.org/mongo-driver/v2/bson"
	"go.mongodb.org/mongo-driver/v2/event"
	"go.mongodb.org/mongo-driver/v2/mongo"
	"go.mongodb.org/mongo-driver/v2/mongo/options"
	"go.mongodb.org/mongo-driver/v2/mongo/readconcern"
	"go.mongodb.org/mongo-driver/v2/mongo/readpref"
	"go.mongodb.org/mongo-driver/v2/mongo/writeconcern"
)

type Job struct {
	ID            string    `bson:"_id" json:"id"`
	Tenant        string    `bson:"tenant" json:"tenant"`
	Title         string    `bson:"title" json:"title"`
	State         string    `bson:"state" json:"state"`
	CreatedAt     time.Time `bson:"createdAt" json:"createdAt"`
	Version       int64     `bson:"version" json:"version"`
	SchemaVersion int32     `bson:"schemaVersion" json:"schemaVersion"`
}
type Auth struct {
	Username string `json:"username"`
	Password string `json:"password"`
	Source   string `json:"source"`
}
type CreateInput struct {
	ID     string `json:"id"`
	Tenant string `json:"tenant"`
	Title  string `json:"title"`
}

// One complete bounded JSON object: suffixes must be consumed before any DB call.
func decodeCreate(w http.ResponseWriter, r *http.Request) (CreateInput, error) {
	var in CreateInput
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, 4096))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&in); err != nil {
		return in, err
	}
	var extra any
	if err := dec.Decode(&extra); err != io.EOF {
		return in, errors.New("body must contain exactly one bounded JSON object")
	}
	if len(in.ID) < 1 || len(in.ID) > 80 || len(in.Tenant) < 1 || len(in.Tenant) > 80 || len(in.Title) < 1 || len(in.Title) > 200 {
		return in, errors.New("invalid bounded id/tenant/title")
	}
	return in, nil
}

var commands atomic.Int64

func main() {
	mode := flag.String("mode", "serve", "serve, seed, migrate, measure, check, transaction or bson")
	n := flag.Int("n", 20000, "seed document count or measurement iterations")
	hint := flag.String("hint", "", "measurement only: natural or an index name")
	flag.Parse()
	if *mode == "bson" {
		raw, err := bson.Marshal(bson.D{{Key: "n", Value: int32(42)}, {Key: "s", Value: "я"}})
		must(err)
		fmt.Printf("%d bytes: %s\n", len(raw), hex.EncodeToString(raw))
		return
	}
	uri := os.Getenv("MONGO_URI")
	if uri == "" {
		uri = "mongodb://127.0.0.1:27117/?replicaSet=study&retryWrites=true"
	}
	opt := options.Client().ApplyURI(uri).SetMaxPoolSize(12).SetMaxConnecting(2).SetServerSelectionTimeout(3 * time.Second).SetConnectTimeout(2 * time.Second).SetTimeout(5 * time.Second)
	if file := os.Getenv("MONGO_AUTH_FILE"); file != "" {
		var a Auth
		b, err := os.ReadFile(file)
		must(err)
		must(json.Unmarshal(b, &a))
		opt.SetAuth(options.Credential{Username: a.Username, Password: a.Password, AuthSource: a.Source})
	}
	opt.SetMonitor(&event.CommandMonitor{Succeeded: func(_ context.Context, e *event.CommandSucceededEvent) { commands.Add(1) }})
	client, err := mongo.Connect(opt)
	must(err)
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		_ = client.Disconnect(ctx)
	}()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	must(client.Ping(ctx, readpref.Primary()))
	cancel()
	db := client.Database("workshop", options.Database().SetWriteConcern(&writeconcern.WriteConcern{W: "majority", Journal: ptr(true)}).SetReadConcern(readconcern.Majority()))
	jobs := db.Collection("jobs")
	switch *mode {
	case "seed":
		// Deterministic IDs make a second run preserve original documents.
		inserted := int64(0)
		for start := 0; start < *n; start += 500 {
			end := start + 500
			if end > *n {
				end = *n
			}
			models := []mongo.WriteModel{}
			for i := start; i < end; i++ {
				j := Job{fmt.Sprintf("seed-%06d", i), fmt.Sprintf("tenant-%02d", i%100), fmt.Sprintf("job %d", i), "open", time.Unix(1700000000+int64(i), 0).UTC(), 1, 1}
				models = append(models, mongo.NewUpdateOneModel().SetFilter(bson.D{{Key: "_id", Value: j.ID}}).SetUpdate(bson.D{{Key: "$setOnInsert", Value: j}}).SetUpsert(true))
			}
			ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
			r, err := jobs.BulkWrite(ctx, models)
			cancel()
			must(err)
			inserted += r.UpsertedCount
		}
		fmt.Printf("new=%d requested=%d\n", inserted, *n)
	case "migrate":
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		r, err := jobs.UpdateMany(ctx, bson.D{{Key: "schemaVersion", Value: 1}}, bson.D{{Key: "$set", Value: bson.D{{Key: "priority", Value: int32(0)}, {Key: "schemaVersion", Value: int32(2)}}}})
		must(err)
		_, err = jobs.Indexes().CreateOne(ctx, mongo.IndexModel{Keys: bson.D{{Key: "tenant", Value: 1}, {Key: "state", Value: 1}, {Key: "createdAt", Value: -1}, {Key: "_id", Value: 1}}, Options: options.Index().SetName("tenant_state_recent")})
		must(err)
		fmt.Printf("matched=%d modified=%d index=tenant_state_recent\n", r.MatchedCount, r.ModifiedCount)
	case "check":
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		total, err := jobs.CountDocuments(ctx, bson.D{})
		must(err)
		bad, err := jobs.CountDocuments(ctx, bson.D{{Key: "version", Value: bson.D{{Key: "$lt", Value: 1}}}})
		must(err)
		fmt.Printf("jobs=%d invalidVersion=%d successfulCommands=%d\n", total, bad, commands.Load())
		if bad != 0 {
			os.Exit(1)
		}
	case "measure":
		if *n < 1 || *n > 10000 {
			log.Fatal("n must be 1..10000")
		}
		samples := make([]float64, 0, *n)
		for i := 0; i < *n; i++ {
			t := time.Now()
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			find := options.Find().SetSort(bson.D{{Key: "createdAt", Value: -1}, {Key: "_id", Value: 1}}).SetLimit(20)
			if *hint == "natural" {
				find.SetHint(bson.D{{Key: "$natural", Value: 1}})
			} else if *hint != "" {
				find.SetHint(*hint)
			}
			cur, err := jobs.Find(ctx, bson.D{{Key: "tenant", Value: "tenant-01"}, {Key: "state", Value: "open"}}, find)
			must(err)
			var result []Job
			err = cur.All(ctx, &result)
			cancel()
			must(err)
			samples = append(samples, float64(time.Since(t).Microseconds())/1000)
		}
		sort.Float64s(samples)
		fmt.Printf("n=%d serial=1 limit=20 p50_ms=%.3f p95_ms=%.3f p99_ms=%.3f successfulCommands=%d\n", *n, samples[(*n-1)*50/100], samples[(*n-1)*95/100], samples[(*n-1)*99/100], commands.Load())
	case "transaction":
		// New request ID: all changes and ledger commit together; callback may replay.
		session, err := client.StartSession()
		must(err)
		defer session.EndSession(context.Background())
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		_, err = session.WithTransaction(ctx, func(sc context.Context) (any, error) {
			id := "transaction-example-1"
			count, err := db.Collection("ledger").CountDocuments(sc, bson.D{{Key: "_id", Value: id}})
			if err != nil {
				return nil, err
			}
			if count != 0 {
				return nil, nil
			}
			r, err := jobs.UpdateOne(sc, bson.D{{Key: "_id", Value: "seed-000001"}, {Key: "state", Value: "open"}}, bson.D{{Key: "$set", Value: bson.D{{Key: "state", Value: "closed"}}}, {Key: "$inc", Value: bson.D{{Key: "version", Value: 1}}}})
			if err != nil {
				return nil, err
			}
			if r.ModifiedCount != 1 {
				return nil, errors.New("precondition: seed-000001 must be open")
			}
			_, err = db.Collection("ledger").InsertOne(sc, bson.D{{Key: "_id", Value: id}, {Key: "job", Value: "seed-000001"}, {Key: "action", Value: "close"}})
			return nil, err
		}, options.Transaction().SetReadConcern(readconcern.Snapshot()).SetWriteConcern(writeconcern.Majority()))
		must(err)
		fmt.Println("transaction accepted; repeated call reads ledger and makes no second close")
	case "serve":
		serve(jobs)
	default:
		log.Fatal("unknown mode")
	}
}
func ptr[T any](v T) *T { return &v }
func must(err error) {
	if err != nil {
		log.Fatal(err)
	}
}
func reply(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
func serve(jobs *mongo.Collection) {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /jobs", func(w http.ResponseWriter, r *http.Request) {
		in, err := decodeCreate(w, r)
		if err != nil {
			reply(w, 400, map[string]string{"error": "invalid bounded id/tenant/title"})
			return
		}
		j := Job{in.ID, in.Tenant, in.Title, "open", time.Now().UTC().Truncate(time.Millisecond), 1, 2}
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		_, err = jobs.InsertOne(ctx, j)
		if mongo.IsDuplicateKeyError(err) {
			var old Job
			if err := jobs.FindOne(ctx, bson.D{{Key: "_id", Value: in.ID}}).Decode(&old); err != nil {
				reply(w, 503, map[string]string{"error": "read unavailable"})
				return
			}
			if old.Tenant != in.Tenant || old.Title != in.Title {
				reply(w, 409, map[string]string{"error": "id reused for different payload"})
				return
			}
			reply(w, 200, old)
			return
		}
		if err != nil {
			reply(w, 503, map[string]string{"error": "write outcome may be unknown; retry same id"})
			return
		}
		reply(w, 201, j)
	})
	mux.HandleFunc("GET /jobs", func(w http.ResponseWriter, r *http.Request) {
		tenant := r.URL.Query().Get("tenant")
		if tenant == "" {
			reply(w, 400, map[string]string{"error": "tenant required"})
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		cur, err := jobs.Find(ctx, bson.D{{Key: "tenant", Value: tenant}, {Key: "state", Value: "open"}}, options.Find().SetSort(bson.D{{Key: "createdAt", Value: -1}, {Key: "_id", Value: 1}}).SetLimit(20))
		if err != nil {
			reply(w, 503, map[string]string{"error": "find unavailable"})
			return
		}
		out := []Job{}
		if err := cur.All(ctx, &out); err != nil {
			reply(w, 503, map[string]string{"error": "cursor unavailable"})
			return
		}
		reply(w, 200, out)
	})
	mux.HandleFunc("POST /jobs/{id}/close", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		id := r.PathValue("id")
		if strings.HasPrefix(id, "seed-") {
			reply(w, 403, map[string]string{"error": "seed records reserved for measurements"})
			return
		}
		res, err := jobs.UpdateOne(ctx, bson.D{{Key: "_id", Value: id}, {Key: "state", Value: "open"}, {Key: "version", Value: int64(1)}}, bson.D{{Key: "$set", Value: bson.D{{Key: "state", Value: "closed"}}}, {Key: "$inc", Value: bson.D{{Key: "version", Value: 1}}}})
		if err != nil {
			reply(w, 503, map[string]string{"error": "update outcome may be unknown; inspect id"})
			return
		}
		reply(w, 200, map[string]int64{"modified": res.ModifiedCount})
	})
	server := &http.Server{Addr: "127.0.0.1:18089", Handler: mux, ReadHeaderTimeout: 2 * time.Second, ReadTimeout: 5 * time.Second, WriteTimeout: 6 * time.Second, IdleTimeout: 30 * time.Second}
	ln, err := net.Listen("tcp", server.Addr)
	must(err)
	log.Printf("listening %s", server.Addr)
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)
	defer signal.Stop(signals)
	must(serveUntilSignal(server, ln, signals))
}

// Wait for Shutdown to drain handlers before main can disconnect MongoDB.
func serveUntilSignal(server *http.Server, ln net.Listener, signals <-chan os.Signal) error {
	served := make(chan error, 1)
	go func() { served <- server.Serve(ln) }()
	select {
	case err := <-served:
		return err
	case <-signals:
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		err := server.Shutdown(ctx)
		if err != nil {
			// Deadline expired: close remaining connections and report failure.
			_ = server.Close()
		}
		serveErr := <-served
		if err != nil {
			return err
		}
		if !errors.Is(serveErr, http.ErrServerClosed) {
			return serveErr
		}
		return nil
	}
}
