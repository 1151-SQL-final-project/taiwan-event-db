"""解析 OPENTIX 活動頁：取出各票區價格與優惠方案（票種）。

頁面裡的資料是 Nuxt 產生的 JavaScript（window.__NUXT__ = (function(a,b,...){return {...}}(值...))）。
這裡用 esprima 把它「解析」成語法樹再取值，不會執行任何下載來的程式碼。
"""
import datetime as dt
import gzip
import json
import pathlib
import re

import esprima

TAIPEI = dt.timezone(dt.timedelta(hours=8))
_NUXT = re.compile(r"window\.__NUXT__\s*=\s*(.*?);?\s*</script>", re.S)
_LD_JSON = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)
_OG_IMAGE = re.compile(r'<meta[^>]*property="og:image"[^>]*content="(https://[^"]+)"')


def _value(node, env):
    t = node.type
    if t == "Literal":
        return node.value
    if t == "Identifier":
        return env.get(node.name)
    if t == "ArrayExpression":
        return [_value(e, env) for e in node.elements]
    if t == "ObjectExpression":
        return {(p.key.name if p.key.type == "Identifier" else p.key.value): _value(p.value, env) for p in node.properties}
    if t == "UnaryExpression":
        if node.operator == "-":
            v = _value(node.argument, env)
            return -v if isinstance(v, (int, float)) else None
        if node.operator == "!":
            return not _value(node.argument, env)
        return None  # void 0 等
    if t == "TemplateLiteral" and not node.expressions:
        return node.quasis[0].value.cooked
    return None


def decode_nuxt(html: str):
    """回傳 __NUXT__ 的資料（dict）；頁面格式不同時回傳 None。"""
    m = _NUXT.search(html)
    if not m:
        return None
    call = esprima.parseScript("x=" + m.group(1)).body[0].expression.right
    if call.type != "CallExpression" or call.callee.type != "FunctionExpression":
        return None
    env = dict(zip((p.name for p in call.callee.params), (_value(a, {}) for a in call.arguments)))
    ret = next((s for s in call.callee.body.body if s.type == "ReturnStatement"), None)
    return _value(ret.argument, env) if ret else None


def _walk_sections(obj, out):
    """找出所有含 pricePlans 的票區。"""
    if isinstance(obj, dict):
        if isinstance(obj.get("pricePlans"), list):
            out.append(obj)
        for v in obj.values():
            _walk_sections(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_sections(v, out)
    return out


def to_taipei(ts):
    return dt.datetime.fromtimestamp(ts, TAIPEI).replace(tzinfo=None) if isinstance(ts, (int, float)) and ts > 0 else None


def parse_page(path: pathlib.Path) -> dict:
    """回傳 {sections: [{price, plans: [{name, details, price, rate, start, end}]}], low, high, sale_start}。
    sale_start 是開賣時間：ld+json 各場次 offers.availabilityStarts（臺北時間）中最早的一個。"""
    html = gzip.decompress(path.read_bytes()).decode("utf-8", errors="replace")
    result = {"sections": [], "low": None, "high": None, "sale_start": None, "image": None}
    if m := _OG_IMAGE.search(html):
        result["image"] = m.group(1)
    for m in _LD_JSON.finditer(html):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for item in data if isinstance(data, list) else [data]:
            offers = item.get("offers") if isinstance(item, dict) else None
            for offer in offers if isinstance(offers, list) else [offers]:
                starts = offer.get("availabilityStarts") if isinstance(offer, dict) else None
                try:
                    sale = dt.datetime.fromisoformat(starts[:19]) if starts else None
                except ValueError:
                    sale = None
                if sale and (result["sale_start"] is None or sale < result["sale_start"]):
                    result["sale_start"] = sale
            if isinstance(offers, dict) and offers.get("lowPrice") is not None:
                lows = [offers["lowPrice"]] + ([result["low"]] if result["low"] is not None else [])
                highs = [offers.get("highPrice", offers["lowPrice"])] + ([result["high"]] if result["high"] is not None else [])
                result["low"], result["high"] = min(lows), max(highs)
    try:
        nuxt = decode_nuxt(html)
    except Exception:  # 頁面格式改了就只用 ld+json 的價格
        nuxt = None
    for section in _walk_sections(nuxt, []) if nuxt else []:
        result["sections"].append({
            "price": section.get("price"),
            "plans": [{
                "name": (p.get("name") or "").strip(),
                "details": (p.get("details") or "").strip(),
                "price": p.get("bestPrice"),
                "rate": p.get("currentDiscount"),
                "start": to_taipei(p.get("onlineStartTime")),
                "end": to_taipei(p.get("onlineEndTime")),
            } for p in section["pricePlans"] if isinstance(p, dict)],
        })
    return result
