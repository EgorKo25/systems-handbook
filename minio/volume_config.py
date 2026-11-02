"""MinIO sources. Registry/publication is integrated only by the main owner."""
CONFIG = dict(
    volume="XXVII",
    short="MinIO",
    title="MinIO: объект, кодированные части и восстановление",
    description="Архивный OSS Server: происхождение, TLS, доступ, история, object IO, healing, pools, резерв и стоимость ресурсов.",
    revision="2 ноября 2026",
    sections=[
        ("Начало", ["00-route"]),
        ("Сервер и сохраняемый стенд", [
            "minio-01-model", "minio-02-supply", "minio-03-workbench",
            "minio-04-first-object"]),
        ("Доступ и история", [
            "minio-05-limited-access", "minio-06-versions-and-unknown-put"]),
        ("Внутреннее хранение", [
            "minio-08-object-io", "minio-07-healing-and-scanner"]),
        ("Размещение и эксплуатация", [
            "minio-09-pools-and-operations", "minio-10-backup-and-recovery",
            "minio-11-capacity-and-performance"]),
        ("Справочник", ["99-glossary"]),
    ],
    base_terms=[],
    term_modules=["reference"],
    command_modules=["reference"],
    diagram_modules=["diagrams"],
    illustration_links=[dict(
        id="minio-four-endpoint-healing",
        title="Четыре диска: GET и запись исправленных shards",
        label="xl.meta · chunk/hash · tmp · публикация")],
    blurb="Официальный source → собственный сервер → объект и права → части/metadata/quorum → восстановление и ресурсы.",
)
