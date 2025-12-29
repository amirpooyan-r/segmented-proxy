# Advanced TCP Behavior

## Overview
This document exists for readers who want a deeper explanation of why
segmentation can feel strong or surprising in practice.
It connects the project’s segmentation experiments to basic TCP behavior.
It is optional reading and is not required to use SegmentedProxy.

## Segmentation and TCP Flow Control (Conceptual)
TCP has flow control so a sender does not overwhelm a receiver.
At a high level, the sender and receiver coordinate how much data can be in
flight at one time.
Both sides may buffer data briefly, then move it along.
Segmentation adds pauses and smaller chunks in that flow.
It does not change TCP itself, but it can change how data is paced.

## Backpressure (High-Level Explanation)
Backpressure means a slow consumer makes the producer slow down.
In TCP, if the receiver reads slowly, the sender naturally sends less.
Delaying reads or writes can therefore slow a sender without any special tricks.
This is a property of TCP’s design, not a hidden proxy feature.

## Timing vs Bandwidth
Latency is the time it takes for data to move from one side to the other.
Throughput is how much data can be delivered over time.
Small delays can feel dramatic because they add waiting between chunks.
Chunking changes the rhythm of delivery, even when total bandwidth is similar.

## Why Segmentation Feels Stronger Than Expected
Humans notice pauses more than smooth flows, so small delays feel large.
Some applications wait for more data before showing progress.
Buffers can fill quickly and then drain slowly, which feels uneven.
These effects make segmentation look stronger than the raw bandwidth loss.

## What This Project Does NOT Control
SegmentedProxy does not control TCP window sizes.
It does not change congestion control algorithms.
It does not alter packet retransmission behavior.
It does not influence network routing decisions.

## Common Misunderstandings
“The proxy is forcing the client to slow down.”
The proxy can pace delivery, but TCP already slows when the receiver is slow.

“Segmentation changes TCP internals.”
Segmentation only changes timing and chunking at the proxy level.
TCP still handles reliability and flow control as usual.

“Delay equals bandwidth limit.”
Delays add waiting time, but they do not permanently cap bandwidth.
The connection can still move fast when data is released.

## Educational Takeaways
Segmentation mainly changes timing, not content or TCP mechanics.
Flow control and backpressure explain many surprising effects.
This understanding helps you interpret the exercises in `docs/LABS.md`.

## Simple Timing Sketch
```text
Sender -> [chunk] ..wait.. [chunk] ..wait.. [chunk] -> Receiver
```
