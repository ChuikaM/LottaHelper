FROM nginx:alpine

WORKDIR /lottahelper/nginx

RUN apk add --no-cache openssl

RUN mkdir -p /var/log/nginx /etc/nginx/ssl

RUN chown -R nginx:nginx /var/log/nginx /etc/nginx/ssl

WORKDIR /lottahelper/nginx

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]