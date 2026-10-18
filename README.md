![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg)

# UDS v3: a modern drum synth on one Tiny Tapeout tile

Work in progress, started 2026-10-18.

UDS v3 is the third version of Juris Vitols's UDS drum synthesizer for [Tiny Tapeout](https://tinytapeout.com):

- 8 channels, each with a fully editable sound;
- inspired by the drums of GusGus, Simian Mobile Disco, Trentemøller and Röyksopp;
- built to fit one 1x1 tile.

| Version | Where it lives |
| --- | --- |
| v1, as submitted (first-order DAC) | [ai-wrangler/tt-uds-1x1](https://github.com/ai-wrangler/tt-uds-1x1) |
| v2 (second-order DAC, the starting point of this repo) | branch `sd2` of [ai-wrangler/tt-uds-1x1](https://github.com/ai-wrangler/tt-uds-1x1) |
| Browser twin that plays the real Verilog | [UDS-1x1 Virtual](https://ai-wrangler.github.io/uds-virtual/) |

This repo starts from v2: tt-uds-1x1 `sd2` @ 02db483, with the top module renamed to `tt_um_ai_wrangler_uds3`.

- [Datasheet](docs/info.md)
- [v3 brief](docs/v3/BRIEF.md)
- [Contract: SPI and sound parameters](docs/v3/CONTRACT.md)
- [Build tracker](../../issues/1)
