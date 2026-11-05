// A tiny stand-in for the browser DOM, just enough for site/js/dom.js and views.js. It records what
// the views create, so tests can check that untrusted text only ever becomes text nodes and that
// only http(s) links get an href. It has no HTML parser at all: if a view tried innerHTML, the
// test would see a plain property, never new elements.

class FakeNode {
  constructor(nodeType) { this.nodeType = nodeType; this.childNodes = []; this.parentNode = null; }
  append(...nodes) {
    for (const n of nodes) {
      const node = typeof n === "string" ? new FakeText(n) : n;
      node.parentNode = this;
      this.childNodes.push(node);
    }
  }
  replaceChildren(...nodes) { this.childNodes = []; this.append(...nodes); }
  get textContent() { return this.childNodes.map((c) => c.textContent).join(""); }
  set textContent(v) { this.childNodes = [new FakeText(String(v))]; }
}

class FakeText extends FakeNode {
  constructor(text) { super(3); this.data = text; }
  get textContent() { return this.data; }
}

class FakeElement extends FakeNode {
  constructor(tagName, ns = null) {
    super(1);
    this.tagName = tagName.toUpperCase();
    this.namespaceURI = ns;
    this.attributes = new Map();
    this.dataset = {};
    this.listeners = {};
    this.value = "";
  }
  setAttribute(k, v) { this.attributes.set(k, String(v)); }
  getAttribute(k) { return this.attributes.has(k) ? this.attributes.get(k) : null; }
  hasAttribute(k) { return this.attributes.has(k); }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  get className() { return this.getAttribute("class") || ""; }
  set className(v) { this.setAttribute("class", v); }
}

export function installFakeDom() {
  globalThis.document = {
    createElement: (tag) => new FakeElement(tag),
    createElementNS: (ns, tag) => new FakeElement(tag, ns),
    createTextNode: (text) => new FakeText(text),
  };
}

// Every element under the given nodes (arrays are flattened).
export function allElements(nodes) {
  const out = [];
  const walk = (n) => {
    if (Array.isArray(n)) { n.forEach(walk); return; }
    if (!n || typeof n !== "object") return;
    if (n.nodeType === 1) out.push(n);
    (n.childNodes || []).forEach(walk);
  };
  walk(nodes);
  return out;
}

export function textOf(nodes) {
  return (Array.isArray(nodes) ? nodes.flat(Infinity) : [nodes]).filter(Boolean).map((n) => n.textContent).join(" ");
}
