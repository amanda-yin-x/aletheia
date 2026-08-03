FROM node:22-bookworm-slim AS build
WORKDIR /repo
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/api-client/package.json packages/api-client/package.json
RUN corepack pnpm install --frozen-lockfile
COPY apps/web apps/web
COPY packages/api-client packages/api-client
COPY tokens.css tokens.css
RUN corepack pnpm --filter @aletheia/web build
RUN mkdir -p apps/web/.next/standalone/apps/web/.next && cp -r apps/web/.next/static apps/web/.next/standalone/apps/web/.next/static
EXPOSE 3000
CMD ["node", "apps/web/.next/standalone/apps/web/server.js"]
