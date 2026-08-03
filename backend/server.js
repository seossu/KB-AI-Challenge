require('dotenv').config();
const express = require('express');
const cors = require('cors');

const app = express();
// 💡 다시 .env의 PORT 값을 우선으로 가져오고, 없으면 8080을 쓰도록 수정
const PORT = process.env.PORT || 8080; 

app.use(cors()); 
app.use(express.json()); 

const recommendRoutes = require('./routes/recommend');
app.use('/api/recommend', recommendRoutes);

// 입지 추천 (파이썬 엔진 연결)
const locationRoutes = require('./routes/location');
app.use('/api/location', locationRoutes);

// 대화형 입력 파싱 (OpenAI)
const chatRoutes = require('./routes/chat');
app.use('/api/chat', chatRoutes);

app.get('/', (req, res) => {
  res.send('금융상품 추천 백엔드 서버가 정상 작동 중입니다!');
});

const server = app.listen(PORT, () => {
  console.log(`🚀 서버가 http://localhost:${PORT} 에서 안전하게 실행 중입니다.`);
});

server.on('error', (err) => {
  console.error('❌ 서버 실행 중 에러 발생:', err);
});

process.on('uncaughtException', (err) => {
  console.error('❌ 숨겨진 에러 발생:', err);
});