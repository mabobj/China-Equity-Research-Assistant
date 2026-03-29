# 前端工作台说明

本目录是项目的 Next.js 前端工作台，服务于以下场景：
- 单票研究工作台
- 选股与深筛工作台
- 工作流运行状态与结果查看
- 预留页（`/trades`、`/reviews`）

## 常用命令

安装依赖：

```bash
npm install
```

本地开发：

```bash
npm run dev
```

构建与启动：

```bash
npm run build
npm run start
```

质量检查：

```bash
npm run lint
npm run type-check
npm run test:smoke
```

## 路由说明

- `/`：首页与入口导航
- `/stocks/[symbol]`：单票工作台（优先走 workspace-bundle）
- `/screener`：选股工作台（工作流模式）
- `/trades`：预留页（未启用）
- `/reviews`：预留页（未启用）

## 约束说明

前端规则请以 [frontend/AGENTS.md](./AGENTS.md) 为准。  
涉及 Next.js 版本差异时，请优先查阅 `node_modules/next/dist/docs/` 对应文档。
