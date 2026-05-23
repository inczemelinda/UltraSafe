FROM postgres:17

# Postgres runs these once when the database volume is first initialized.
# Keep SQL under a subdirectory so the ordered migration/seed scripts own execution.
COPY sql/ /docker-entrypoint-initdb.d/sql/
COPY scripts/db_migrate.sh /docker-entrypoint-initdb.d/001_db_migrate.sh
COPY scripts/db_seed_demo.sh /docker-entrypoint-initdb.d/002_db_seed_demo.sh
RUN sed -i 's/\r$//' /docker-entrypoint-initdb.d/001_db_migrate.sh /docker-entrypoint-initdb.d/002_db_seed_demo.sh \
    && chmod +x /docker-entrypoint-initdb.d/001_db_migrate.sh /docker-entrypoint-initdb.d/002_db_seed_demo.sh
