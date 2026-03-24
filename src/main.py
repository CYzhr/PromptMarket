#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PromptMarket - Prompt模板市场
用户可以分享、出售、购买优质Prompt模板
"""

import os
import json
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn


@dataclass
class PromptTemplate:
    """Prompt模板"""
    id: str
    title: str
    description: str
    category: str
    content: str
    variables: List[str]
    author_id: str
    author_name: str
    price: float
    currency: str
    downloads: int
    rating: float
    tags: List[str]
    created_at: str
    updated_at: str


class Database:
    """数据库管理"""
    
    def __init__(self, db_path: str = "data/promptmarket.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Prompt模板表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS prompts (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT DEFAULT 'general',
            content TEXT NOT NULL,
            variables TEXT,
            author_id TEXT NOT NULL,
            author_name TEXT,
            price REAL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            downloads INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            tags TEXT,
            featured INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
        ''')
        
        # 用户表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            name TEXT,
            balance REAL DEFAULT 0,
            created_at TEXT
        )
        ''')
        
        # 购买记录表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            prompt_id TEXT,
            price REAL,
            currency TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (prompt_id) REFERENCES prompts (id)
        )
        ''')
        
        # 评价表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            prompt_id TEXT,
            rating INTEGER,
            comment TEXT,
            created_at TEXT
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_prompt(self, prompt: PromptTemplate) -> str:
        """创建Prompt模板"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO prompts 
        (id, title, description, category, content, variables, author_id, author_name, 
         price, currency, downloads, rating, tags, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            prompt.id, prompt.title, prompt.description, prompt.category,
            prompt.content, json.dumps(prompt.variables), prompt.author_id,
            prompt.author_name, prompt.price, prompt.currency, prompt.downloads,
            prompt.rating, json.dumps(prompt.tags), prompt.created_at, prompt.updated_at
        ))
        
        conn.commit()
        conn.close()
        
        return prompt.id
    
    def get_prompts(self, category: str = None, search: str = None, 
                    limit: int = 50, offset: int = 0) -> List[Dict]:
        """获取Prompt列表"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM prompts WHERE 1=1"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if search:
            query += " AND (title LIKE ? OR description LIKE ? OR tags LIKE ?)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term, search_term])
        
        query += " ORDER BY downloads DESC, rating DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_prompt(self, prompt_id: str) -> Optional[Dict]:
        """获取单个Prompt"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,))
        row = cursor.fetchone()
        conn.close()
        
        return self._row_to_dict(row) if row else None
    
    def _row_to_dict(self, row) -> Dict:
        """转换行为字典"""
        if not row:
            return None
        
        d = dict(row)
        if d.get('variables'):
            d['variables'] = json.loads(d['variables'])
        if d.get('tags'):
            d['tags'] = json.loads(d['tags'])
        
        return d
    
    def increment_downloads(self, prompt_id: str):
        """增加下载次数"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE prompts SET downloads = downloads + 1 WHERE id = ?",
            (prompt_id,)
        )
        conn.commit()
        conn.close()


class PromptMarket:
    """Prompt市场应用"""
    
    def __init__(self):
        self.db = Database()
        self.app = FastAPI(title="PromptMarket", version="1.0.0")
        
        self.app.mount("/static", StaticFiles(directory="static"), name="static")
        self.templates = Jinja2Templates(directory="templates")
        
        self.setup_routes()
        self.seed_data()
    
    def seed_data(self):
        """填充示例数据"""
        prompts = self.db.get_prompts(limit=1)
        if len(prompts) == 0:
            # 添加示例Prompt
            sample_prompts = [
                PromptTemplate(
                    id=str(uuid.uuid4()),
                    title="AI写作助手",
                    description="专业的AI写作Prompt，支持文章、博客、营销文案",
                    category="writing",
                    content="你是一位专业的{{role}}。请帮我写一篇关于{{topic}}的{{type}}，风格要{{style}}，字数约{{length}}字。",
                    variables=["role", "topic", "type", "style", "length"],
                    author_id="system",
                    author_name="PromptMarket官方",
                    price=0,
                    currency="USD",
                    downloads=0,
                    rating=4.8,
                    tags=["写作", "内容创作", "免费"],
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat()
                ),
                PromptTemplate(
                    id=str(uuid.uuid4()),
                    title="代码审查专家",
                    description="专业的代码审查Prompt，自动检测bug和优化建议",
                    category="coding",
                    content="你是一位资深{{language}}开发者。请审查以下代码：\n\n```{{language}}\n{{code}}\n```\n\n请提供：\n1. 潜在bug\n2. 性能优化建议\n3. 代码风格改进\n4. 安全问题",
                    variables=["language", "code"],
                    author_id="system",
                    author_name="PromptMarket官方",
                    price=0,
                    currency="USD",
                    downloads=0,
                    rating=4.9,
                    tags=["编程", "代码审查", "免费"],
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat()
                ),
                PromptTemplate(
                    id=str(uuid.uuid4()),
                    title="商业计划书生成器",
                    description="自动生成专业商业计划书，包含市场分析、财务预测",
                    category="business",
                    content="你是一位资深商业顾问。请为以下项目生成一份完整的商业计划书：\n\n项目名称：{{project_name}}\n行业：{{industry}}\n目标市场：{{target_market}}\n核心优势：{{advantages}}\n\n请包含：执行摘要、市场分析、竞争分析、营销策略、财务预测、风险评估。",
                    variables=["project_name", "industry", "target_market", "advantages"],
                    author_id="system",
                    author_name="PromptMarket官方",
                    price=9.99,
                    currency="USD",
                    downloads=0,
                    rating=4.7,
                    tags=["商业", "创业", "付费"],
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat()
                )
            ]
            
            for prompt in sample_prompts:
                self.db.create_prompt(prompt)
    
    def setup_routes(self):
        """设置路由"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def index(request: Request, category: str = None, search: str = None):
            """首页"""
            prompts = self.db.get_prompts(category=category, search=search)
            
            categories = [
                {"id": "writing", "name": "写作", "icon": "✍️"},
                {"id": "coding", "name": "编程", "icon": "💻"},
                {"id": "business", "name": "商业", "icon": "💼"},
                {"id": "education", "name": "教育", "icon": "📚"},
                {"id": "creative", "name": "创意", "icon": "🎨"},
            ]
            
            return self.templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "prompts": prompts,
                    "categories": categories,
                    "current_category": category,
                    "search": search
                }
            )
        
        @self.app.get("/prompt/{prompt_id}", response_class=HTMLResponse)
        async def prompt_detail(request: Request, prompt_id: str):
            """Prompt详情页"""
            prompt = self.db.get_prompt(prompt_id)
            
            if not prompt:
                raise HTTPException(status_code=404, detail="Prompt not found")
            
            return self.templates.TemplateResponse(
                "detail.html",
                {"request": request, "prompt": prompt}
            )
        
        @self.app.get("/api/prompts")
        async def get_prompts(category: str = None, search: str = None, limit: int = 50):
            """获取Prompt列表API"""
            prompts = self.db.get_prompts(category=category, search=search, limit=limit)
            return JSONResponse(prompts)
        
        @self.app.get("/api/prompt/{prompt_id}")
        async def get_prompt(prompt_id: str):
            """获取单个Prompt API"""
            prompt = self.db.get_prompt(prompt_id)
            
            if not prompt:
                return JSONResponse({"error": "Not found"}, status_code=404)
            
            # 增加下载次数
            self.db.increment_downloads(prompt_id)
            
            return JSONResponse(prompt)
    
    def run(self):
        """运行应用"""
        print("启动 PromptMarket...")
        print("访问地址：http://0.0.0.0:8001")
        
        uvicorn.run(self.app, host="0.0.0.0", port=8001)


def main():
    app = PromptMarket()
    app.run()


if __name__ == "__main__":
    main()
