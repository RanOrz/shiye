(() => {
  const getMeta = (...selectors) => {
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      const value =
        element?.getAttribute("content") ||
        element?.getAttribute("datetime") ||
        element?.getAttribute("href") ||
        element?.textContent;
      if (value?.trim()) return value.trim();
    }
    return "";
  };

  const getAllMeta = (selector) =>
    [...document.querySelectorAll(selector)]
      .map((element) => element.getAttribute("content")?.trim())
      .filter(Boolean);

  const cleanText = (value) => value.replace(/\s+/g, " ").trim();

  const inlineText = (node) =>
    [...node.childNodes].map((child) => toMarkdown(child, { inline: true })).join("").trim();

  const tableToMarkdown = (table) => {
    const rows = [...table.querySelectorAll("tr")]
      .map((row) => [...row.querySelectorAll(":scope > th, :scope > td")].map((cell) => cleanText(cell.textContent || "")))
      .filter((row) => row.length);
    if (!rows.length) return "";
    const width = Math.max(...rows.map((row) => row.length));
    const normalized = rows.map((row) => [...row, ...Array(width - row.length).fill("")]);
    const escape = (value) => value.replace(/\|/g, "\\|");
    const output = [
      `| ${normalized[0].map(escape).join(" | ")} |`,
      `| ${Array(width).fill("---").join(" | ")} |`,
    ];
    normalized.slice(1).forEach((row) => output.push(`| ${row.map(escape).join(" | ")} |`));
    return `${output.join("\n")}\n\n`;
  };

  const toMarkdown = (node, context = {}) => {
    if (node.nodeType === Node.TEXT_NODE) {
      return context.pre ? node.textContent : (node.textContent || "").replace(/\s+/g, " ");
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return "";

    const tag = node.tagName.toLowerCase();
    const children = () => [...node.childNodes].map((child) => toMarkdown(child, context)).join("");
    if (["script", "style", "noscript", "template", "svg", "canvas", "button", "form"].includes(tag)) return "";
    if (/^h[1-6]$/.test(tag)) return `${"#".repeat(Number(tag[1]))} ${inlineText(node)}\n\n`;
    if (tag === "p") return `${children().trim()}\n\n`;
    if (tag === "br") return "  \n";
    if (tag === "hr") return "\n---\n\n";
    if (tag === "strong" || tag === "b") return `**${children().trim()}**`;
    if (tag === "em" || tag === "i") return `*${children().trim()}*`;
    if (tag === "del" || tag === "s") return `~~${children().trim()}~~`;
    if (tag === "code" && node.parentElement?.tagName.toLowerCase() !== "pre") return `\`${node.textContent}\``;
    if (tag === "pre") return `\n\`\`\`\n${(node.textContent || "").trim()}\n\`\`\`\n\n`;
    if (tag === "blockquote") {
      const body = children().trim().split("\n").map((line) => `> ${line}`).join("\n");
      return `${body}\n\n`;
    }
    if (tag === "a") {
      const label = children().trim() || cleanText(node.textContent || "");
      const href = node.href || "";
      return href && !href.startsWith("javascript:") ? `[${label}](${href})` : label;
    }
    if (tag === "img") {
      const src = node.currentSrc || node.src || "";
      return src ? `![${node.alt || ""}](${src})` : "";
    }
    if (tag === "ul" || tag === "ol") {
      const ordered = tag === "ol";
      const items = [...node.children]
        .filter((child) => child.tagName.toLowerCase() === "li")
        .map((item, index) => {
          const value = [...item.childNodes]
            .filter((child) => !(child.nodeType === Node.ELEMENT_NODE && ["ul", "ol"].includes(child.tagName.toLowerCase())))
            .map((child) => toMarkdown(child, context))
            .join("")
            .trim();
          const nested = [...item.children]
            .filter((child) => ["ul", "ol"].includes(child.tagName.toLowerCase()))
            .map((child) => toMarkdown(child, context).trim().split("\n").map((line) => `  ${line}`).join("\n"))
            .join("\n");
          return `${ordered ? `${index + 1}.` : "-"} ${value}${nested ? `\n${nested}` : ""}`;
        });
      return `${items.join("\n")}\n\n`;
    }
    if (tag === "table") return tableToMarkdown(node);
    if (["article", "main", "section", "div", "header", "footer", "aside", "figure", "figcaption", "details", "summary", "dl", "dt", "dd"].includes(tag)) {
      return `${children()}${context.inline ? "" : "\n"}`;
    }
    return children();
  };

  const selected = window.getSelection();
  let sourceRoot;
  if (selected && !selected.isCollapsed && cleanText(selected.toString()).length > 30) {
    sourceRoot = document.createElement("div");
    for (let index = 0; index < selected.rangeCount; index += 1) {
      sourceRoot.appendChild(selected.getRangeAt(index).cloneContents());
    }
  } else {
    const candidate = document.querySelector("article, main, [role='main'], .post-content, .article-content, .entry-content") || document.body;
    sourceRoot = candidate.cloneNode(true);
  }

  sourceRoot
    .querySelectorAll("script, style, noscript, template, nav, footer, aside, form, button, input, select, textarea, iframe, [aria-hidden='true'], .advertisement, .ads, .cookie-banner, .comments")
    .forEach((element) => element.remove());

  const markdown = toMarkdown(sourceRoot)
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  const canonical = document.querySelector('link[rel="canonical"]')?.href || location.href;
  const published = getMeta(
    'meta[property="article:published_time"]',
    'meta[name="date"]',
    'meta[name="pubdate"]',
    "time[datetime]"
  );
  const tags = [
    ...getAllMeta('meta[property="article:tag"]'),
    ...getAllMeta('meta[name="keywords"]')
      .flatMap((value) => value.split(/[,，]/))
      .map((value) => value.trim()),
  ];

  return {
    title: getMeta('meta[property="og:title"]', 'meta[name="twitter:title"]') || document.title || "未命名网页",
    author: getMeta('meta[name="author"]', 'meta[property="article:author"]', '[rel="author"]'),
    published: published ? published.slice(0, 10) : "",
    description: getMeta('meta[name="description"]', 'meta[property="og:description"]'),
    source: canonical,
    site: getMeta('meta[property="og:site_name"]') || location.hostname,
    tags: [...new Set(tags.filter(Boolean))].slice(0, 12),
    content: markdown || cleanText(sourceRoot.textContent || ""),
    words: cleanText(sourceRoot.textContent || "").length,
  };
})();
