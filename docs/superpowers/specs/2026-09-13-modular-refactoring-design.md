# Bookeeper 模块化重构设计文档

## 1. 项目概述

**项目名称：** Bookeeper 模块化重构  
**创建日期：** 2026-09-13  
**版本：** 1.0  
**状态：** 设计完成，待实施

### 1.1 背景
Bookeeper 是一个个人图书管理工具，包含 PyQt6 桌面应用和 FastAPI Web 服务。当前代码存在架构不够模块化、配置管理简单、错误处理分散、缺少测试等问题。

### 1.2 目标
- 实现模块化架构，提高代码可维护性
- 统一配置管理和错误处理
- 添加测试覆盖，确保代码质量
- 保持功能完整性，不考虑向后兼容性

## 2. 架构设计

### 2.1 整体架构
```
bookeeper/
├── core/                    # 核心业务逻辑
│   ├── models/              # 数据模型
│   ├── repositories/        # 数据访问层
│   └── services/            # 业务服务
├── ui/                      # PyQt6 界面层
├── web/                     # FastAPI Web 服务
├── utils/                   # 工具函数
└── config/                  # 配置管理
```

### 2.2 数据层设计
```
core/
├── models/
│   ├── book.py              # Book 数据模型
│   └── base.py              # 基础模型类
├── repositories/
│   ├── base.py              # Repository 基类
│   ├── book_repo.py         # Book 专用仓储
│   └── interface.py         # Repository 接口
└── services/
    ├── douban.py            # 豆瓣API服务
    ├── backup.py            # 备份服务
    ├── covers.py            # 封面缓存服务
    └── undo.py              # 撤销管理服务
```

### 2.3 UI层设计
```
ui/
├── main_window.py           # 主窗口
├── components/              # 可复用组件
│   ├── book_form.py         # 图书编辑表单
│   ├── book_table.py        # 图书表格
│   ├── search_bar.py        # 搜索栏
│   ├── toolbar.py           # 工具栏
│   └── status_bar.py        # 状态栏
├── dialogs/                 # 对话框
│   ├── detail_dialog.py     # 详情对话框
│   ├── search_dialog.py     # 搜索对话框
│   ├── stats_dialog.py      # 统计对话框
│   └── about_dialog.py      # 关于对话框
├── views/                   # 视图
│   ├── table_view.py        # 表格视图
│   └── cover_wall.py        # 封面墙视图
└── theme.py                 # 主题管理
```

### 2.4 配置管理设计
```
config/
├── __init__.py              # 配置管理器
├── defaults.py              # 默认配置值
├── schema.py                # 配置验证模式
└── env.py                   # 环境变量处理
```

**配置层次（优先级从高到低）：**
1. 环境变量
2. 用户配置文件（`config.json`）
3. 默认配置（`defaults.py`）

### 2.5 错误处理和日志设计
```
core/
├── exceptions.py            # 自定义异常类
└── logging.py               # 日志配置模块
```

**异常层次：**
```python
BookeeperError              # 基础异常
├── DatabaseError            # 数据库相关错误
├── ServiceError             # 服务相关错误
└── ValidationError          # 数据验证错误
```

### 2.6 测试设计
```
tests/
├── unit/                    # 单元测试
├── integration/             # 集成测试
├── fixtures/                # 测试数据
└── conftest.py              # pytest 配置
```

### 2.7 Web服务设计
```
web/
├── app.py                   # FastAPI 应用工厂
├── routes/                  # 路由模块
│   ├── books.py             # 图书相关路由
│   ├── covers.py            # 封面代理路由
│   └── stats.py             # 统计路由
└── middleware/               # 中间件
    ├── auth.py              # 认证中间件
    └── logging.py           # 日志中间件
```

### 2.8 容器化部署设计
```
├── Dockerfile               # Docker 镜像构建
├── docker-compose.yml       # Docker Compose 编排
├── .dockerignore            # Docker 忽略文件
└── deploy/                  # 部署配置
    └── nginx.conf           # Nginx 反向代理配置（可选）
```

**Docker 镜像设计：**
- 基础镜像：`python:3.12-slim`（轻量级）
- 多阶段构建：分离构建环境和运行环境
- 非 root 用户：安全考虑，使用非特权用户运行
- 健康检查：添加容器健康检查端点

**Docker Compose 编排：**
- 服务：bookeeper（主应用）、nginx（可选反向代理）
- 卷挂载：数据库、配置文件、备份目录持久化
- 网络：内部网络隔离，端口映射
- 环境变量：通过 `.env` 文件或环境变量注入配置

**部署策略：**
- 开发环境：`docker-compose up` 一键启动
- 生产环境：使用预构建镜像或自行构建
- 数据备份：定期备份容器内的数据库卷
- 日志管理：容器日志收集和轮转

## 3. 实施顺序

1. **基础架构**：配置管理、异常定义、日志配置
2. **数据层**：Repository 模式、服务层重构
3. **业务逻辑**：核心服务（豆瓣、备份、封面缓存）
4. **UI层**：组件化重构、信号分离
5. **Web层**：路由分离、中间件
6. **测试**：单元测试、集成测试
7. **容器化**：Docker 镜像构建、Docker Compose 编排
8. **文档**：代码文档、API文档、部署文档

## 4. 关键改进点

### 4.1 配置管理
- 配置验证：添加配置项验证
- 环境变量支持：通过环境变量覆盖配置
- 热重置：支持运行时重新加载配置
- 类型安全：使用 dataclass 管理配置项

### 4.2 错误处理
- 统一异常类型和错误处理策略
- 结构化日志：使用 JSON 格式
- 分级日志：不同模块不同日志级别
- 上下文信息：记录操作上下文

### 4.3 测试策略
- 单元测试：覆盖核心业务逻辑，使用 mock 隔离外部依赖
- 集成测试：验证组件间协作，使用真实数据库
- 测试覆盖率：目标 70%+ 核心代码

## 5. 风险评估

### 5.1 技术风险
- 重构过程中可能引入新 bug
- 模块边界划分不当可能导致循环依赖
- 测试覆盖不足可能遗漏问题

### 5.2 缓解措施
- 分阶段实施，每个阶段完成后测试验证
- 使用接口抽象，明确定义模块边界
- 逐步增加测试覆盖率，优先测试核心功能

## 6. 成功标准

1. 架构清晰，模块职责单一
2. 配置管理灵活，支持环境变量
3. 错误处理统一，日志结构化
4. 测试覆盖率达到 70%+ 核心代码
5. 所有现有功能正常工作
6. 代码可维护性和可扩展性显著提高
7. Docker 镜像可正常构建和运行
8. Docker Compose 可一键部署完整环境