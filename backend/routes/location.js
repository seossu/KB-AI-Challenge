const express = require('express');
const router = express.Router();
const { spawn } = require('child_process');
const path = require('path');

// 파이썬 추천 엔진 경로 (backend 기준 상위의 location-scoring)
const PY_DIR = path.resolve(__dirname, '..', '..', 'location-scoring');
const PY_ENTRY = path.join(PY_DIR, 'api_entry.py');
const PYTHON = process.env.PYTHON_BIN || 'python3';

/*
 * POST /api/location
 * body: 1팀 입력 JSON (business_type, preferred_region, capital, ... + 설문 필드)
 * → 파이썬 api_entry.py 를 spawn, stdin 으로 JSON 전달, stdout JSON 수신
 */
router.post('/', (req, res) => {
  const input = JSON.stringify(req.body || {});
  const py = spawn(PYTHON, [PY_ENTRY], { cwd: PY_DIR });

  let out = '';
  let err = '';
  py.stdout.on('data', (d) => (out += d));
  py.stderr.on('data', (d) => (err += d)); // 파이썬 경고/진행로그 (무시 가능)

  py.on('error', (e) =>
    res.status(500).json({ ok: false, reason: `파이썬 실행 실패: ${e.message}` })
  );

  py.on('close', (code) => {
    // 파이썬은 마지막 줄에 JSON 을 출력 (앞줄은 진행 로그일 수 있음)
    const lastLine = out.trim().split('\n').filter(Boolean).pop() || '';
    try {
      const json = JSON.parse(lastLine);
      return res.status(200).json(json);
    } catch (e) {
      return res.status(500).json({
        ok: false,
        reason: '파이썬 출력 파싱 실패',
        exitCode: code,
        stderr: err.slice(-400),
        stdout: out.slice(-400),
      });
    }
  });

  py.stdin.write(input);
  py.stdin.end();
});

module.exports = router;
