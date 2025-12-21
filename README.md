# SegmentedProxy

A lightweight educational HTTPS proxy with safe defaults, DNS resolution, and optional segmentation strategies.

### Known Limitations

- Chunked Transfer-Encoding is forwarded verbatim and not reassembled.
- Streaming chunk extensions are not interpreted.
- Designed for correctness and transparency, not performance.

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).
See the LICENSE file for details.