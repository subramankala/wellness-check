FROM node:20-alpine

WORKDIR /workspace

COPY apps/ops-console/package.json apps/ops-console/package-lock.json* /workspace/apps/ops-console/
RUN cd /workspace/apps/ops-console && npm install

CMD ["sleep", "infinity"]
