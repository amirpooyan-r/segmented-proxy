# FAQ

This page answers common questions about SegmentedProxy behavior and concepts.
It is written for beginners and intermediate learners.

## Segmentation Does Not Seem to Work

### “I enabled segmentation, but nothing looks different.”

This is the most common situation.

Possible reasons:

* The response is very small
* The chunk size is larger than the response
* No delay is configured
* The rule does not match the request

**What to try:**

* Use a smaller `chunk` size (for example, 128 or 256 bytes)
* Add a small `delay` (for example, 20–50 ms)
* Test with a larger response (downloads are easier to observe)

---

## HTTPS Traffic Is Not Being Segmented

### “Segmentation works for HTTP, but not for HTTPS.”

This is expected unless your rule matches the `CONNECT` method.

For HTTPS:

* Segmentation applies **only** to `CONNECT` tunnels
* The proxy does **not** decrypt TLS
* After `CONNECT`, only encrypted bytes are forwarded

**Check your rule:**

```text
scheme=https,method=CONNECT
```

If `method=CONNECT` is missing, the rule will not affect HTTPS traffic.

---

## HTTP Requests Are Segmented Unexpectedly

### “My HTTP requests are segmented even though I didn’t specify a method.”

For HTTP traffic:

* If no `method` is specified, the rule applies to **all methods**
* This includes `GET`, `POST`, `PUT`, and others

**How to limit it:**

```text
method=POST
```

This restricts segmentation to only the chosen method.

---

## Segmentation Works Sometimes but Not Always

### “The behavior feels inconsistent.”

This can happen when:

* Using the `random` strategy
* Responses vary in size
* Network timing changes between requests

This is normal behavior.

**What to remember:**

* Random segmentation creates **non-uniform patterns**
* Small responses may finish before segmentation is visible

---

## I See Only One Chunk in the Logs

### “Why do I see a single forwarded chunk?”

Possible reasons:

* The response is smaller than `chunk`
* The connection closes before more data arrives

**Example:**
If `chunk=1024` and the response is only 300 bytes,
only one chunk will be sent.

---

## Delay Makes Everything Feel Very Slow

### “Even a small delay has a big effect.”

This is expected.

Delays:

* add latency between chunks
* can strongly affect perceived speed
* do not change bandwidth, only timing

This is useful for learning how applications react to slow delivery.

---

## Segmentation Does Not Change the Content

### “Is the data modified?”

No.

Segmentation:

* does **not** change content
* does **not** inspect encrypted data
* only changes **timing and grouping**

If content appears broken, check the client or upstream server.

---

## Is This a DPI Bypass or Privacy Tool?

No.

SegmentedProxy is:

* a teaching and testing tool
* not a DPI bypass
* not a traffic hiding system
* not a MITM proxy

It helps you **understand** traffic behavior, not evade inspection.

---

## Common Rule Mistakes

### Rule Order

Rules are evaluated in order.
If an earlier rule matches, later rules are ignored.

**Check:**

* Block rules
* Direct rules
* Upstream rules

---

### Chunk Size Too Large

Large chunks may hide segmentation effects.

**Tip:**
Start small, then increase gradually.

---

## When to Check Logs

Logs are often more reliable than visual behavior.

Use logs to:

* confirm rule matching
* see forwarded chunk sizes
* verify delays are applied

---

## Still Confused?

If something still feels unclear:

1. Re-read **SEGMENTATION.md**
2. Try **LABS.md**
3. Reduce your rule to the simplest form
4. Observe logs carefully

Most confusion disappears with simpler rules.
