# The API needs Python 3.10+ (PEP 604 unions in the Pydantic models); hosts
# still on 3.8 cannot even import it. This image exists to carry a modern
# interpreter, nothing else — there is no service to run, no extension to
# compile, and every wheel in requirements.txt is prebuilt.
FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/api/requirements.txt

# policy.py sits at the repo root, not inside api/, because scripts/ shares it.
# config.py puts that root on sys.path relative to its own location, so the
# layout here has to mirror the repo's — see api/CLAUDE.md.
COPY policy.py /app/policy.py
COPY api/ /app/api/

# The database is 242 MB, changes independently of the code, and is gitignored:
# it is bind-mounted at run time, never baked in.
ENV MLOSMETADB_PATH=/data/mlosmetadb.db

WORKDIR /app/api
EXPOSE 8000

# Binding to 0.0.0.0 is safe here because the port is published to 127.0.0.1
# only (see the run command in DEPLOY.md) — the container's own interface is
# not reachable from outside the host.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
