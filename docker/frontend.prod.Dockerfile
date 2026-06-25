FROM node:22-alpine AS build

ARG VITE_DEBUG=false
ARG VITE_API_URL
ARG VITE_FRONTEND_URL

ENV VITE_DEBUG=${VITE_DEBUG}
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_FRONTEND_URL=${VITE_FRONTEND_URL}

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

COPY docker/nginx.frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80
