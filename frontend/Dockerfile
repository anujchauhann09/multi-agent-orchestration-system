# stage 1 — build
FROM node:20-alpine AS builder

WORKDIR /app

# copy package files from frontend/ (build context is project root)
COPY frontend/package*.json ./
RUN npm ci

# copy frontend source
COPY frontend/ .
RUN npm run build

# stage 2 — serve with Nginx
FROM nginx:alpine

# remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# copy nginx config
COPY infrastructure/nginx/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
