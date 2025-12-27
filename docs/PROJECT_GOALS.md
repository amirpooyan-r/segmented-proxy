# Project Goals and Non-Goals

This page explains what SegmentedProxy is designed to do, and what it is **not**
designed to do. This helps users understand the scope of the project.

---

## Project Goals

SegmentedProxy is an **educational project**.

Its main goals are:

- Teach how HTTP and HTTPS proxies work
- Explain CONNECT tunnels in HTTPS
- Show how rule-based routing works
- Demonstrate traffic segmentation techniques
- Help users experiment safely on local networks
- Provide clear, readable, and well-documented code
- Be easy to read and understand for beginners
- Focus on correctness, clarity, and learning

The project prefers:
- Simple design over complex optimization
- Explainable behavior over hidden magic
- Safe defaults
- Clear error messages

---

## Non-Goals

SegmentedProxy is **not** intended to be:

- Production-ready proxy software
- A censorship circumvention tool
- A DPI bypass or evasion system
- A high-performance or high-throughput proxy
- A replacement for tools like Squid, mitmproxy, or Envoy
- A security or anonymity product
- A full-featured enterprise proxy

Advanced DPI systems may detect or block segmentation techniques.
This project does **not** attempt to defeat such systems.

---

## Intended Audience

This project is best suited for:

- Students learning networking
- Developers new to proxies
- People curious about HTTP/HTTPS internals
- Learners experimenting in lab or home environments

---

## Summary

If you want to **learn how proxies work**, SegmentedProxy is a good fit.

If you want a **production or privacy-focused proxy**, this project is **not**
the right tool.
