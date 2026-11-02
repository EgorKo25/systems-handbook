# Reader must prebuild bin/ledger-api for the target Linux architecture.
FROM scratch
COPY --chown=65532:65532 bin/ledger-api /ledger-api
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/ledger-api"]
