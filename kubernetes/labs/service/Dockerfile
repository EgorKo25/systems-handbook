FROM scratch
COPY --chown=65532:65532 ledger-api /ledger-api
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/ledger-api"]
