# Segmentation

## What Segmentation Means Here
In this project, segmentation means sending data in small parts.
The proxy splits bytes into chunks.
It can add a small delay between chunks.

## Fixed vs Random Segmentation
- Fixed: the chunk size stays the same.
- Random: the chunk size changes within a range.

## Why Experiment With It
- To see how chunking changes traffic shape.
- To learn how proxies can change timing and size.
- To understand limits of simple techniques.

## It Is Not a Guaranteed DPI Bypass
Segmentation is not a bypass tool.
This is not a bypass guide.
Modern DPI can still detect patterns.
Networks can block or slow traffic.

## Segmentation and DPI (Educational Note)
DPI systems look at many signals.
They can use timing, sizes, and flow patterns.
Splitting data does not hide everything.

## References
- Cloudflare DPI: https://www.cloudflare.com/learning/security/glossary/deep-packet-inspection-dpi/
- Traffic analysis: https://www.cloudflare.com/learning/privacy/what-is-traffic-analysis/
