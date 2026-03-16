---
name: schema-exploration
description: 用于发现和理解数据库结构、表、列和关系
---

# 模式探索技能

## 何时使用此技能

当你需要以下操作时使用此技能：
- 理解数据库结构
- 找到包含某些类型数据的表
- 发现列名和数据类型
- 映射表之间的关系
- 回答诸如"有哪些表可用？"或"Customer 表有哪些列？"的问题

## 工作流

### 1. 列出所有表
使用 `sql_db_list_tables` 工具查看数据库中所有可用的表。

这将返回你可以查询的完整表列表。

### 2. 获取特定表的模式
使用 `sql_db_schema` 工具和表名来检查：
- **列名** - 有哪些字段可用
- **数据类型** - INTEGER、TEXT、DATETIME 等
- **示例数据** - 3 行示例以了解内容
- **主键** - 行的唯一标识符
- **外键** - 与其他表的关系

### 3. 映射关系
识别表如何连接：
- 寻找以"Id"结尾的列（例如 CustomerId、ArtistId）
- 外键链接到其他表的主键
- 记录父子关系

### 4. 回答问题
提供关于以下方面的清晰信息：
- 可用的表及其用途
- 列名及其包含的内容
- 表之间的关系
- 示例数据以说明内容

## 示例："有哪些表可用？"

**步骤 1：** 使用 `sql_db_list_tables`

**返回结果：**
```
Chinook 数据库有 11 个表：
1. Artist - 音乐艺术家
2. Album - 音乐专辑
3. Track - 单曲
4. Genre - 音乐流派
5. MediaType - 文件格式（MP3、AAC 等）
6. Playlist - 用户创建的播放列表
7. PlaylistTrack - 播放列表中的曲目
8. Customer - 商店客户
9. Employee - 商店员工
10. Invoice - 客户购买记录
11. InvoiceLine - 发票中的单个项目
```

## 示例："Customer 表有哪些列？"

**步骤 1：** 使用 `sql_db_schema` 并指定表名 "Customer"

**返回结果：**
```
Customer 表有以下列：

- CustomerId (INTEGER) - 主键，唯一客户 ID
- FirstName (NVARCHAR) - 客户名
- LastName (NVARCHAR) - 客户姓
- Company (NVARCHAR) - 公司名称（可选）
- Address、City、State、Country、PostalCode - 地址字段
- Phone (NVARCHAR) - 电话号码
- Fax (NVARCHAR) - 传真号码
- Email (NVARCHAR) - 电子邮件地址
- SupportRepId (INTEGER) - 指向 Employee 表的外键

示例数据显示客户包括：
- 来自巴西的 Luís Gonçalves
- 来自德国的 Leonie Köhler
- 来自加拿大的 François Tremblay
```

## 示例："如何按艺术家统计收入？"

**步骤 1：** 确定需要的表
- Artist（有艺术家名称）
- Album（将艺术家与曲目关联）
- Track（将专辑与销售关联）
- InvoiceLine（有销售数据）
- Invoice（有收入总计）

**步骤 2：** 映射关系
```
Artist (ArtistId)
  ↓ 1:many
Album (ArtistId, AlbumId)
  ↓ 1:many
Track (AlbumId, TrackId)
  ↓ 1:many
InvoiceLine (TrackId, UnitPrice, Quantity)
```

**返回结果：**
```
要按艺术家统计收入，你需要：
1. 从 Artist 表开始
2. 通过 ArtistId JOIN 到 Album
3. 通过 AlbumId JOIN 到 Track
4. 通过 TrackId JOIN 到 InvoiceLine
5. 对收入求和（UnitPrice * Quantity）
6. 按艺术家名称 GROUP BY

这需要使用 query-writing 技能来执行。
```

## 质量指南

**对于"列出表"的问题：**
- 显示所有表名
- 添加每个表内容的简要描述
- 将相关表分组（例如音乐目录、交易、人员）

**对于"描述表"的问题：**
- 列出所有列及其数据类型
- 解释每个列包含的内容
- 显示示例数据以便理解
- 标注主键和外键
- 解释与其他表的关系

**对于"如何查询 X"的问题：**
- 确定需要的表
- 映射 JOIN 路径
- 解释关系链
- 建议后续步骤（使用 query-writing 技能）

## 常见探索模式

### 模式 1：找表
"哪个表有客户信息？"
→ 使用 list_tables，然后描述 Customer 表

### 模式 2：理解结构
"Invoice 表里有什么？"
→ 使用 schema 工具显示列和示例数据

### 模式 3：映射关系
"艺术家如何与销售关联？"
→ 追踪外键链：Artist → Album → Track → InvoiceLine → Invoice

## 提示

- Chinook 中的表名是单数且大写（Customer，不是 customers）
- 外键通常有"Id"后缀，并与表名匹配
- 使用示例数据来了解值的外观
- 当不确定使用哪个表时，先列出所有表
