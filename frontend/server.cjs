const express = require('express');
const path = require('path');

const app = express();
const startedAt = Date.now();
const PORT = Number(process.env.PORT || 3080);
const APP_NAME = process.env.APP_NAME || 'rex-os-frontend';
const APP_SHA = process.env.APP_SHA || 'dev';

app.get('/health', (_req, res) => {
  res.status(200).json({
    status: 'healthy',
    app: APP_NAME,
    sha: APP_SHA,
    uptime_seconds: Math.floor((Date.now() - startedAt) / 1000),
  });
});

app.use(express.static(path.join(__dirname, 'dist')));
app.get('*', (_req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`[rex-os-frontend] listening on ${PORT}`);
});
