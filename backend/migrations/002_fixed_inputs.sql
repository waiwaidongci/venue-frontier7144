-- Schema v2：效率研究增加固定投入（非可自由处置投入）分类。
-- 新库由 SQLAlchemy metadata 直接建列；此脚本供已存在的 v1 库升级，JSON 列默认空数组，
-- 旧研究读取为空列表即“全可调整投入”，求解与指纹口径保持 v1 不变。
ALTER TABLE efficiency_runs ADD COLUMN IF NOT EXISTS fixed_inputs JSON NOT NULL DEFAULT '[]';
SELECT 'venue-frontier schema v2: fixed_inputs added';
