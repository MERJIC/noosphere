#!/usr/bin/env python3
"""
一次性脚本：从所有概念页 frontmatter tags 中移除 pattern/XXX 标签。

用法：
  python3 scripts/remove_pattern_tags.py --dry-run   预览改动，不写回
  python3 scripts/remove_pattern_tags.py             执行移除
"""

import argparse
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_ROOT = os.path.dirname(SCRIPT_DIR)
CONCEPT_DIR = os.path.join(LIB_ROOT, "概念页")


def remove_pattern_from_tags(content):
    """
    从 frontmatter tags 中移除 pattern/XXX 标签。
    返回 (修改后的内容, 被移除的 pattern 值或 None)。
    """
    # 匹配 frontmatter
    m = re.match(r'^(---\s*\n)(.*?)(\n---)', content, re.DOTALL)
    if not m:
        return content, None

    fm_header = m.group(1)
    fm_body = m.group(2)
    fm_footer = m.group(3)
    rest = content[m.end():]

    # 找到 tags 行
    lines = fm_body.split('\n')
    new_lines = []
    removed_pattern = None

    for line in lines:
        stripped = line.strip()
        # 匹配 tags: [...] 格式
        if re.match(r'^tags:\s*\[', stripped):
            # 提取 tags 数组
            m_tags = re.match(r'^tags:\s*\[(.+)\]\s*$', stripped)
            if m_tags:
                tags_str = m_tags.group(1)
                # 解析各个 tag
                tags = [t.strip() for t in tags_str.split(',')]
                new_tags = []
                for t in tags:
                    if t.startswith('pattern/'):
                        removed_pattern = t
                    else:
                        new_tags.append(t)
                # 重建 tags 行
                new_line = f"tags: [{', '.join(new_tags)}]"
                new_lines.append(new_line)
                continue
        new_lines.append(line)

    new_fm = '\n'.join(new_lines)
    new_content = fm_header + new_fm + fm_footer + rest
    return new_content, removed_pattern


def main():
    parser = argparse.ArgumentParser(description="移除概念页 pattern 标签")
    parser.add_argument('--dry-run', action='store_true', help='预览改动，不写回')
    args = parser.parse_args()

    modified = 0
    skipped = 0
    patterns_removed = {}

    for fname in sorted(os.listdir(CONCEPT_DIR)):
        if not fname.endswith('.md') or fname == 'INDEX.md':
            continue
        fpath = os.path.join(CONCEPT_DIR, fname)
        if not os.path.isfile(fpath):
            continue

        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()

        new_content, removed = remove_pattern_from_tags(content)

        if removed:
            concept_name = fname[:-3]
            # 统计
            pattern_val = removed.replace('pattern/', '')
            patterns_removed[pattern_val] = patterns_removed.get(pattern_val, 0) + 1

            if args.dry_run:
                print(f"  [DRY] {concept_name}: 移除 {removed}")
            else:
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(new_content)

            modified += 1
        else:
            skipped += 1

    print(f"\n处理完成")
    print(f"  修改: {modified} 个文件")
    print(f"  跳过（无 pattern 标签）: {skipped} 个")

    if patterns_removed:
        print(f"\n移除的 pattern 分布:")
        for p, cnt in sorted(patterns_removed.items(), key=lambda x: -x[1]):
            print(f"  pattern/{p}: {cnt} 个")

    if args.dry_run:
        print(f"\n⚠ DRY RUN 模式 — 未写回任何文件")


if __name__ == '__main__':
    main()
