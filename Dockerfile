
# Stage 1: 构建前端
FROM node:18-alpine AS frontend
WORKDIR /app/web_ui
COPY web_ui/package.json web_ui/yarn.lock ./
RUN yarn install --frozen-lockfile
COPY web_ui/ .
RUN npm run build

# Stage 2: 后端
FROM  --platform=$BUILDPLATFORM ghcr.io/rachelos/base-full:latest AS werss-base
#

ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
# ENV PIP_INDEX_URL=https://mirrors.huaweicloud.com/repository/pypi/simple

# 复制Python依赖文件
FROM werss-base
COPY requirements.txt .
# 安装系统依赖
WORKDIR /app
RUN echo "1.0.$(date +%Y%m%d.%H%M)">>docker_version.txt
# 复制后端代码
ADD ./config.example.yaml  ./config.yaml
ADD . .
# 用前端构建阶段的产物覆盖 static/
COPY --from=frontend /app/web_ui/dist/ ./static/
RUN chmod +x install.sh
RUN chmod +x start.sh

# 暴露端口
EXPOSE 8001
CMD ["/app/start.sh"]
