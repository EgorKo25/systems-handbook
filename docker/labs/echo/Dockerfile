# syntax=docker/dockerfile:1
# Pass an explicitly selected official Go image (preferably repository@digest).
ARG GO_IMAGE
FROM --platform=$BUILDPLATFORM ${GO_IMAGE} AS build
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
RUN --mount=type=cache,target=/root/.cache/go-build \
    GOTOOLCHAIN=local go test ./...
ARG TARGETOS
ARG TARGETARCH
RUN --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH GOTOOLCHAIN=local \
    go build -mod=readonly -trimpath -buildvcs=false -o /out/echo ./cmd/echo
FROM scratch
COPY --from=build /out/echo /echo
USER 10001:10001
EXPOSE 8080
STOPSIGNAL SIGTERM
ENTRYPOINT ["/echo"]
