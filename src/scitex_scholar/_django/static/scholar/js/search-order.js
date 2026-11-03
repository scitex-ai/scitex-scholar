/* Sorting of loaded search rows only; provider ranking and pagination stay
 * server-owned. Original entry indices preserve DOI/title selection keys. */
(function (root) {
  "use strict";
  const prefixes = { year: "year", citations: "citations", impact_factor: "impact" };
  function nextOrder(order, field) {
    if (field === "title") return order === "title" ? "relevance" : "title";
    const prefix = prefixes[field];
    if (!prefix) throw new Error("Unknown search sorter");
    return order === `${prefix}-desc` ? `${prefix}-asc`
      : order === `${prefix}-asc` ? "relevance" : `${prefix}-desc`;
  }
  function direction(order, field) {
    if (field === "title") return order === "title" ? "asc" : "none";
    const prefix = prefixes[field];
    return order === `${prefix}-desc` ? "desc" : order === `${prefix}-asc` ? "asc" : "none";
  }
  function numeric(value) {
    if (value === null || value === undefined || typeof value === "boolean" || (typeof value === "string" && value.trim() === "")) return null;
    const number = Number(value);
    return Number.isFinite(number) && number >= 0 ? number : null;
  }
  function sourceNames(paper) {
    const values = Array.isArray(paper.source_engines) ? paper.source_engines.slice() : [];
    if (typeof paper.source === "string") values.push(paper.source);
    return [...new Set(values.filter((value) => typeof value === "string" && value.trim()).map((value) => value.trim()))];
  }
  function sortEntries(entries, order) {
    if (order === "relevance") return entries.slice();
    if (order === "title") return entries.slice().sort((a, b) =>
      String(a.paper.title || "").localeCompare(String(b.paper.title || "")) || a.index - b.index);
    const fields = { year: "year", citations: "citation_count", impact: "impact_factor" };
    const match = /^(year|citations|impact)-(asc|desc)$/.exec(order);
    if (!match) throw new Error("Unknown search order");
    const field = fields[match[1]], sign = match[2] === "asc" ? 1 : -1;
    return entries.slice().sort((a, b) => {
      const av = numeric(a.paper[field]), bv = numeric(b.paper[field]);
      if (av === null || bv === null) return av === bv ? a.index - b.index : av === null ? 1 : -1;
      return (av - bv) * sign || a.index - b.index;
    });
  }
  root.ScholarSearchOrder = Object.freeze({ nextOrder, direction, sortEntries, sourceNames });
})(globalThis);
