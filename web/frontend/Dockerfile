FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
# VITE_API_URL must be set as a Railway build variable
ARG VITE_API_URL=https://daily-news-podcast-production.up.railway.app
ENV VITE_API_URL=$VITE_API_URL
RUN echo "Building with VITE_API_URL=$VITE_API_URL" && npm run build

FROM node:20-alpine
WORKDIR /app
RUN npm install -g serve
COPY --from=builder /app/dist ./dist
EXPOSE 3000
CMD ["sh", "-c", "serve -s dist -l ${PORT:-3000}"]
