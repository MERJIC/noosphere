---

## name: "knowledge-cards"
description: "将知识内容（圆桌讨论、多视角对话、哲学概念等）改写为可传播的 3:4 卡片格式 HTML。用户说传播版知识卡片做成卡片可传播格式发到小红书时触发。"

# Knowledge Cards · 知识传播卡片

## 触发条件

用户说以下任意内容时执行本 skill：

- "传播版""做成可传播的格式"
- "知识卡片""卡片格式"
- "小红书卡片""做成图文"
- "发到小红书""传播用"

---

## 设计原则

以下原则是所有版式的共同根基。

### P1. 可读性是底线

底色和文字色的对比度必须充足。深底白字，浅底黑字。不存在「深底灰字」或「浅底白字」。

### P2. 内容不妥协

传播版和留档版的区别在表达方式，不在内容深度。专业术语保留，读者能跟上逻辑。

### P3. 封面是钩子

封面不写人名、不写目录、不写摘要。用一句直击核心困惑的话让读者想翻下去。小红书是信息流，封面只有一秒的窗口。

### P4. 品牌水印低调

右下角 MERJIC，字体 ZY LOYALTY，小到不影响阅读，但能辨认。品牌存在感来自内容质量，不来自水印大小。

### P5. 排版为内容服务

没有 ASCII 图表（小卡片上排版不可控）。每张卡只有一个焦点——内容本身。

### P6. 不套格式，做判断

本文件记录的是经过验证的参数和版式参考，不是必须填的表。内容不同，卡片数量、底色节奏、结构编排都应该灵活调整。理解规则背后的「为什么」，比遵守规则本身更重要。

---

## 版式注册表

版式之间是平行关系，各自有独立的设计逻辑。生成时选一个版式，读对应的 DESIGN.md，从该设计语言出发编排。

### 选择逻辑

- 黑橙白：默认版式，通用场景。衬线标题 + 极细字重 + 人物颜色系统 + 橘色强调
- Apple：自信精致、大量留白、极低密度。无衬线标题 600 weight + Action Blue 唯一强调色
- Claude：温暖文学、编辑排版。衬线标题（Cormorant Garamond）+ 珊瑚色 scarce 强调 + 引文斜体
- xAI：纯黑宇宙感。纯色块人物标识 + 固定四色 + hairline 分割

### 共性规范

| 项目 | 值 |
|------|-----|
| 尺寸 | 375×500px（3:4，小红书标准） |
| 品牌水印 | ZY LOYALTY，9px，0.06em |
| PDF 导出 | `window.print()`（html2canvas 在深色背景上有不可修复的颜色 bug） |
| 输出路径 | `output/知识卡片/YYYY-MM-DD-[主题]-cards.html` |

### 黑橙白

| 项目 | 值 |
|------|-----|
| CSS | `reference/merjic-swiss-dark-card-style.css` |
| DESIGN.md | 无（原则内联） |
| 字体 | Inter 200/300 + JetBrains Mono + ZY LOYALTY |
| 底色 | dark(#0A0A0A) / paper(#FAFAF8) / accent(#E0620A) |
| 特征 | 人物颜色系统贯穿圆点/竖线/高亮。深浅交替，综述橘色，首尾深色 |
| 人名格式 | 阵容卡：`中文全名  英文全名`（双空格）；发言/对话卡：`中文简称 · 英文简称`；正文纯中文 |

### Apple

| 项目 | 值 |
|------|-----|
| CSS | `reference/merjic-apple-card-style.css` |
| DESIGN.md | `个人总部/skills/design-reference/design-systems/apple.md` |
| 字体 | Inter 400/600 + Noto Sans SC + JetBrains Mono + ZY LOYALTY |
| 底色 | white(#FFF) / parchment(#F5F5F7) / dark(#272729) / dark-alt(#2A2A2C) / black(#000) |
| 强调色 | 橘色(#E0620A)，浅色版 #FF8040 |
| 特征 | 标题 600 weight + 负字间距。极低密度，每张卡一个核心观点。无人物颜色系统。speaker-name 12px 中文。pill 按钮 border-radius:9999px |
| 人名格式 | 阵容卡：`中文全名  英文全名`（双空格）+ 下一行 t-fine 写领域；发言卡：`中文简称 · 领域`；对话卡：`中文简称` |
| Footer | position: absolute 底部对齐，padding 0 32px 18px，与正文边框齐平 |

### Claude

| 项目 | 值 |
|------|-----|
| CSS | 内联 |
| DESIGN.md | `个人总部/skills/design-reference/design-systems/claude.md` |
| 字体 | Cormorant Garamond（衬线标题）+ Inter 400/500 + JetBrains Mono + ZY LOYALTY |
| 底色 | canvas(#FAF9F5) / card-surface(#EFE9DE) / dark(#181715) / coral(#CC785C) |
| 强调色 | coral(#CC785C)，scarce 使用——只用分隔线和综述卡 |
| 特征 | 衬线标题 400 weight + 负字间距。衬线斜体引言块配左侧 hairline 竖线。11.5px uppercase 标签。coral italic 高亮。无人物颜色系统。无圆角、无阴影、无渐变 |

### xAI

| 项目 | 值 |
|------|-----|
| CSS | `reference/merjic-xai-cosmic-card-style.css` |
| DESIGN.md | `个人总部/skills/design-reference/design-systems/xai.md` |
| 底色 | canvas(#0A0A0A) / canvas-soft(#1A1C20) 双色交替 |
| 特征 | 全部 400 weight，标题负字距。人物纯色块 8×8px + 固定四色（breeze/twilight/sunset/dusk）。hairline 分割，无阴影。人名与领域紧邻，无分隔符。左上角标签中文 |

---

## 内容改写规范

### 专业词汇

保留，第一次出现时紧跟一句话解释，后续直接使用。

### 叙述视角

人物发言用第一人称，主持/综述用第三人称或无人称。一张卡片内不混用。

### 禁用结构

- 否定排比、公式化结尾、学术标注（"核心命题""核心挑战"）
- 简言之/总而言之总结框——核心观点融入正文
- 论点条目化——还原成发言现场，不要列表

### 圆桌语气分化

每位发言者有不同的语气节奏。第一人称直接说立场，不用"我认为""我觉得"缓冲。

---

## 技术规范

### HTML 生成

将 CSS 内联到 `<style>` 标签（不用外链，保证离线可用和导出完整）。

### 导出方案

**PDF：必须用浏览器原生 `window.print()`。** 浏览器原生打印走 Chrome 自身渲染引擎，颜色、字体、CJK 排版（引号间距等）100% 精确。

**ZIP 图片：用 html-to-image + JSZip，禁止使用 html2canvas。**

原因：html2canvas 会自己重绘一遍 DOM，导致以下问题：
- 深色背景上白色文字渲染为黑色（不可修复的颜色 bug）
- **CJK 排版丢失**——全角/半角空格、`&nbsp;`、CSS padding/margin 在内联元素中的间距全部被吞掉或渲染不一致
- 嵌套 `<span>` 的样式丢失

html-to-image 走 SVG foreignObject 路径，直接复用浏览器原生渲染结果——页面上看到什么，导出就是什么。CDN 用 UMD 版本（`dist/html-to-image.js`），全局作用域下调用 `htmlToImage.toPng(element, { pixelRatio: 2 })`。

```js
// 标准导出脚本模板
<script src="https://cdn.jsdelivr.net/npm/html-to-image@1.11.11/dist/html-to-image.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
<script>
async function exportZip() {
  const btn = event.target;
  const origText = btn.textContent;
  btn.textContent = '导出中...';
  btn.disabled = true;
  const cards = document.querySelectorAll('.card');
  const zip = new JSZip();
  const promises = Array.from(cards).map(async (card, i) => {
    try {
      const dataUrl = await htmlToImage.toPng(card, { pixelRatio: 2, cacheBust: true });
      const res = await fetch(dataUrl);
      const blob = await res.blob();
      zip.file(`card-${String(i+1).padStart(2,'0')}.png`, blob);
    } catch(e) { console.warn(`Card ${i+1} failed:`, e); }
  });
  await Promise.all(promises);
  const content = await zip.generateAsync({ type: 'blob' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(content);
  a.download = '[主题]-cards.zip';
  a.click();
  URL.revokeObjectURL(a.href);
  btn.textContent = origText;
  btn.disabled = false;
}
</script>
```

必须包含 `@media print` 规则：`.card` / `.tile` 上必须有 `print-color-adjust: exact; -webkit-print-color-adjust: exact`，否则打印时背景色消失。

### ZY LOYALTY 字体

- 备份：`个人总部/output/知识卡片/fonts/ZY Loyalty.ttf`
- 版权属字节跳动，跨平台分发存在法律风险，仅用于品牌水印（6 个字母），风险可控

### 人物选择

不限于 scholar-dict 中的学者。可加入 influencer、公众人物、行业实践者。scholar-dict 仅用于名字拼写对照。

---

## 质检清单

- [ ] `print-color-adjust: exact` 已设置
- [ ] 底色和文字色对比度充足（深底无黑字/灰字，浅底无白字）
- [ ] 封面是钩子问句，不写人名
- [ ] 品牌水印 9px，只写 MERJIC
- [ ] 内容不溢出 375×500px
- [ ] 无 ASCII 图表
- [ ] `@media print` 规则完整

---

## 生成流程

1. 确定使用哪个版式
2. 读取对应的 DESIGN.md（在 `个人总部/skills/design-reference/design-systems/` 下）
3. 从 DESIGN.md 的设计语言出发编排卡片，不套其他版式的原则
4. 内容（圆桌讨论文本）不变，呈现方式随版式变化
5. 导出统一用 `window.print()`
6. 文件保存到 `output/知识卡片/YYYY-MM-DD-[主题]-cards.html`

告知用户：
- 浏览器打开 → 点「导出 PDF」→ 打印对话框选「另存为 PDF」
- 每卡一页，纸张自动适配 375×500px
- 如需 ZIP 图片包，点「导出图片 ZIP」（需 html2canvas 支持）

&nbsp;
