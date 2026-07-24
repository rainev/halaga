# Development image for the Vite dev server (hot-reload).
FROM node:22-alpine

WORKDIR /app

# Install deps first so this layer caches unless package.json changes.
COPY package.json ./
RUN npm install

# App source is bind-mounted in dev (see docker-compose.yml).
EXPOSE 4000

CMD ["npm", "run", "dev", "--", "--host"]
