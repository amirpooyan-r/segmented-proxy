# LABS: Learning Segmentation by Observation

These labs are designed to help you **see and feel** how segmentation works in
practice.
You do not need deep networking knowledge to follow them.

The goal is **observation**, not performance testing or traffic bypassing.

These labs focus on observing *delivery behavior*.
They do not change content and do not inspect encrypted traffic.
For HTTPS, segmentation applies only to CONNECT tunnels.

---

## Before You Start

### Requirements

* SegmentedProxy running locally
* Basic familiarity with editing `rules.txt`
* A browser or `curl`

### What to Watch

During these labs, pay attention to:

* proxy logs
* timing differences
* how data appears to arrive

You are not expected to inspect packets or decrypt traffic.

---

## Lab 1: Fixed Segmentation vs No Segmentation

### Goal

Understand how fixed-size chunks change delivery behavior.

### Setup

1. Start with **no segmentation rule** for a test domain.

2. Make a request and note:

   * how fast the response appears
   * how logs look

3. Now add a fixed segmentation rule:

```text
*.example.com=segment_upstream,strategy=fixed,chunk=256
```

### Observe

* The response may appear in **small steps**
* Logs may show multiple forwarded chunks
* The content is the same, but the delivery feels different

### What You Learn

Segmentation affects **how data arrives**, not **what data arrives**.

---

## Lab 2: Adding Delay Between Chunks

### Goal

See how timing affects applications.

### Setup

Modify the rule:

```text
*.example.com=segment_upstream,strategy=fixed,chunk=256,delay=50
```

### Observe

* Pages may load more slowly
* Text or data may appear gradually
* The browser may show loading indicators longer

### What You Learn

Small delays can strongly influence perceived speed,
even without changing bandwidth.

---

## Lab 3: Random vs Fixed Segmentation

### Goal

Compare predictable vs unpredictable chunking.

### Setup

Use a random strategy:

```text
*.example.com=segment_upstream,strategy=random,min=128,max=1024,delay=10
```

### Observe

* Chunk sizes vary
* Timing feels less regular
* Logs show uneven forwarding

### What You Learn

Different segmentation strategies create different delivery patterns.

---

## Lab 4: HTTPS and CONNECT-only Segmentation

### Goal

Understand where segmentation applies for HTTPS.

### Setup

Use a CONNECT-only rule:

```text
*.example.com=segment_upstream,scheme=https,method=CONNECT,strategy=fixed,chunk=512
```

### Observe

* Only HTTPS traffic is affected
* HTTP requests remain unchanged
* Encrypted content is never inspected

### What You Learn

For HTTPS, segmentation applies to the **tunnel**, not the content.

---

## Lab 5: When Segmentation Seems to Do Nothing

### Goal

Learn common reasons why effects are not visible.

### Try This

* Use a very large chunk size
* Use a fast, small response
* Remove delay

### Observe

* No visible difference
* Fewer log entries

### What You Learn

Segmentation effects depend on:

* data size
* timing
* rule matching

Sometimes “nothing happens” is the expected result.

---

## Key Takeaways

* Segmentation changes **delivery behavior**, not content
* Effects are easier to see with:

  * larger responses
  * smaller chunks
  * added delays
* HTTPS segmentation works only through `CONNECT`
* Rules control *where* segmentation applies


If segmentation effects feel subtle at first, that is normal.
This project is designed to teach observation and understanding,
not to produce dramatic visual changes.