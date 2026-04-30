FROM node:20.19-alpine AS build

WORKDIR /app
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY frontend/frontend/package*.json ./
RUN npm ci

COPY frontend/frontend ./
RUN npm run build

FROM nginx:1.27-alpine

ENV API_UPSTREAM=http://api:8000
COPY frontend/frontend/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
