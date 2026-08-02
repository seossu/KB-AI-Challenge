# Node.js가 기본으로 깔려있는 Debian 기반 이미지 사용
FROM node:18-bullseye-slim

# 파이썬3 및 pip 설치
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Node.js 패키지 설치
COPY backend/package*.json ./backend/
RUN cd backend && npm install

# Python 패키지 설치 
# (requirements.txt가 최상단에 있으므로 이를 복사해서 설치)
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# 프로젝트 전체 코드 복사 (backend와 location-scoring 모두 포함)
COPY . .

# Node.js 서버 실행 위치로 이동
WORKDIR /app/backend

# 백엔드 포트 개방
EXPOSE 8080

# 백엔드 실행 (package.json의 시작 명령어나 메인 파일명에 맞게 수정하세요)
CMD ["node", "server.js"]