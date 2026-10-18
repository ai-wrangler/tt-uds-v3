/*
 * UDS v3 voice engine. Bit-exact with model/uds3_model.py.
 *
 * All voice state is one shift register, the ring: 2 words of 64 bits that
 * move one bit per clock, so each voice passes the end of the ring once per
 * 128-clock frame. While voice v's word passes (window v, t = 0..63), its
 * envelopes and phase are updated bit-serially and written back into the
 * start of the ring.
 *
 * Word layout, in the order the bits leave the ring (bit t leaves at clock t):
 *    0-7  pitch     P0[7:0]       MSB first, as sent
 *    8-11 decay     P1[7:4]
 *   12-13 wave      P1[3:2]
 *   14-15 color     P1[1:0]
 *   16-18 bend      P2[7:5]
 *   19-21 btime     P2[4:2]
 *   22-23 mode      P2[1:0]
 *   24-26 mix       P3[7:5]
 *   27-29 channel   LSB first
 *   30-31 zero
 *   32-39 env       LSB first      main envelope
 *   40-47 aux       LSB first      aux envelope: bend, split decay, clap
 *   48-63 phase     LSB first
 *
 * SPDX-License-Identifier: Apache-2.0
 */
`default_nettype none

module uds3_core (
    input  wire       clk,
    input  wire       rst_n,

    input  wire       hit_cmd,
    input  wire       stop,
    input  wire [2:0] hit_ch,
    input  wire       byte_done,
    input  wire [2:0] byte_idx,
    input  wire [7:0] hold,

    output wire       audio,
    output wire       busy,
    output wire       frame_sync
);

  localparam L  = 64;
  localparam NL = 2 * L;

  // ------------------------------------------------------------------ timing
  reg  [5:0]  t;
  reg         v;
  reg  [12:0] frame;
  reg         clearing;
  wire        wend = &t;
  wire        fend = wend & v;
  wire [2:0]  r    = t[5:3];
  wire [2:0]  j    = t[2:0];

  always @(posedge clk) begin
    if (!rst_n) begin
      {frame, v, t} <= 20'd0;
      clearing      <= 1'b1;
    end else begin
      {frame, v, t} <= {frame, v, t} + 20'd1;
      if (fend) clearing <= 1'b0;
    end
  end

  // -------------------------------------------------------------------- ring
  reg  [NL-1:0] ring;
  reg           tail;
  wire          head = ring[NL-1];
  always @(posedge clk) ring <= {ring[NL-2:0], tail};

  // clock 0 of a window: bit b of the voice is ring[NL-1-b]
  // last clock of a window: bit b of the next voice is ring[NL-2-b]
  wire [L-1:0] w0, nw;
  genvar gb;
  generate
    for (gb = 0; gb < L; gb = gb + 1) begin : g_taps
      assign w0[gb] = ring[NL-1-gb];
      assign nw[gb] = ring[NL-2-gb];
    end
  endgenerate

  // ------------------------------------------ clock 0: envelope step flags
  wire [3:0] z_decay = {w0[8], w0[9], w0[10], w0[11]};
  wire [2:0] z_bt    = {w0[19], w0[20], w0[21]};
  wire       z_lin   = w0[22] & w0[23];                 // mode 3: clap
  wire [7:0] z_env   = w0[39:32];
  wire [7:0] z_aux   = w0[47:40];
  wire [3:0] z_ad    = z_lin ? {1'b0, z_bt} : {1'b0, z_bt} + 4'd3;
  reg  [3:0] tz;                                     // trailing zeros of frame, at most 13
  integer k;
  always @(*) begin
    tz = 4'd13;
    for (k = 12; k >= 0; k = k - 1) if (frame[k]) tz = k[3:0];
  end

  reg c_dec, c_adec, c_elt8, c_alt8, c_lin;
  always @(posedge clk) begin
    if (t == 6'd0) begin
      c_dec  <= (|z_env) & (tz >= z_decay | z_decay > 4'd13);
      c_adec <= (|z_aux) & (tz >= z_ad);
      c_elt8 <= z_env[7:3] == 5'd0;
      c_alt8 <= z_aux[7:3] == 5'd0;
      c_lin  <= z_lin;
    end
  end

  // ------------------------------------- last clock: next voice's sound values
  wire [7:0] n_pitch = {nw[0], nw[1], nw[2], nw[3], nw[4], nw[5], nw[6], nw[7]};
  wire [1:0] n_wave  = {nw[12], nw[13]};
  wire [1:0] n_color = {nw[14], nw[15]};
  wire [2:0] n_bend  = {nw[16], nw[17], nw[18]};
  wire [1:0] n_mode  = {nw[22], nw[23]};
  wire [2:0] n_mix   = {nw[24], nw[25], nw[26]};
  wire [7:0] n_env   = nw[39:32];
  wire [7:0] n_aux   = nw[47:40];
  wire [9:0] n_ph    = nw[63:54];                       // phase[15:6]

  // pitch + bend x aux / 16, at most 255
  wire [10:0] prod   = ({3'd0, n_aux} & {11{n_bend[0]}}) +
                       ({2'd0, n_aux, 1'b0} & {11{n_bend[1]}}) +
                       ({1'd0, n_aux, 2'b0} & {11{n_bend[2]}});
  wire [8:0]  pe_raw = {1'b0, n_pitch} + {2'b00, prod[10:4]};
  wire [7:0]  n_pe   = pe_raw[8] ? 8'hFF : pe_raw[7:0];

  // oscillator
  wire [8:0] fold  = n_ph[8:0] ^ {9{n_ph[9]}};
  wire [8:0] trw   = {~fold[8], fold[7:0]};
  wire [8:0] drv   = (trw[8] ^ trw[7]) ? {trw[8], {8{~trw[8]}}} : {trw[7:0], 1'b0};
  wire       sqb   = n_wave[0] ? (n_ph[9] ^ frame[0] ^ frame[2]) : n_ph[9];
  wire [8:0] n_tone = n_wave == 2'd0 ? trw :
                      n_wave == 2'd1 ? drv :
                      sqb ? 9'h100 : 9'h0FF;

  // amplitudes of the tone and the noise
  wire [7:0] cmp_b   = (n_mode == 2'd3) ? {n_aux[5:0], 2'b11} : n_aux;
  wire [7:0] n_min   = (n_env < cmp_b) ? n_env : cmp_b;
  wire [7:0] n_at    = (n_mode == 2'd1) ? n_min : n_env;
  wire [7:0] n_an    = (n_mode == 2'd2 || (n_mode == 2'd3 && n_aux[7:6] != 2'd0)) ? n_min : n_env;

  reg [7:0] c_pe, c_at, c_an;
  reg [8:0] c_tone;
  reg [2:0] c_mix;
  reg [1:0] c_color;
  always @(posedge clk) begin
    if (wend) begin
      c_pe    <= n_pe;
      c_tone  <= n_tone;
      c_at    <= n_at;
      c_an    <= n_an;
      c_mix   <= n_mix;
      c_color <= n_color;
    end
  end

  // ------------------------------------------ bit-serial envelopes and phase
  // env (r = 4) and aux (r = 5) share one subtractor: x -= max(x >> 3, 1),
  // or x -= 1 for aux in clap mode. Bit j + 3 of the field is ring[NL-4].
  reg        bor;
  wire       is_aux  = r[0];
  wire       sml   = is_aux ? (c_alt8 | c_lin) : c_elt8;
  wire       d_bit   = sml ? (j == 3'd0) : (ring[NL-4] & (j <= 3'd4));
  wire       bor_in  = (j == 3'd0) ? 1'b0 : bor;
  wire       sub_out = head ^ d_bit ^ bor_in;

  // phase += (32 + pe[4:0]) << pe[7:5]
  reg        cy;
  wire [3:0] pj      = t[3:0];
  wire [4:0] pk      = {1'b0, pj} - {2'b00, c_pe[7:5]};
  wire [5:0] mant    = {1'b1, c_pe[4:0]};
  wire       inc_bit = !pk[4] && pk[3:0] <= 4'd5 && mant[pk[2:0]];
  wire       cy_in   = (pj == 4'd0) ? 1'b0 : cy;
  wire       ph_new  = head ^ inc_bit ^ cy_in;

  always @(posedge clk) begin
    bor <= (~head & (d_bit | bor_in)) | (d_bit & bor_in);
    cy  <= (head & inc_bit) | (head & cy_in) | (inc_bit & cy_in);
  end

  // ------------------------------------------------------ HITs and commits
  // A HIT command picks the target voice at the next frame end. Each patch
  // byte is then written into the target's word in the target's next window;
  // P0 also silences it, P3 writes mix, channel, env, aux and phase.
  reg        pend, tgt, hv, con, kill, kill_pend;
  reg  [2:0] cb;
  reg        choice;

  assign busy       = pend | hv;
  assign frame_sync = ~v;

  always @(posedge clk) begin
    if (!rst_n) begin
      pend <= 1'b0; hv <= 1'b0; con <= 1'b0;
      kill <= 1'b0; kill_pend <= 1'b0; tgt <= 1'b0; cb <= 3'd0;
    end else begin
      if (hit_cmd) pend <= 1'b1;
      else if (fend && pend) begin pend <= 1'b0; tgt <= choice; end
      if (byte_done) hv <= 1'b1;
      if (wend) begin
        if (hv && !pend && v != tgt) begin
          con <= 1'b1; cb <= byte_idx;
        end else if (con) begin
          con <= 1'b0; hv <= 1'b0;
        end
      end
      kill_pend <= stop | (kill_pend & !fend);
      if (fend) kill <= kill_pend;
    end
  end

  // commit bit and whether this clock writes it
  reg cbit, cwr;
  always @(*) begin
    cbit = 1'b0;
    cwr  = 1'b0;
    case (cb)
      3'd1: begin cwr = (r == 3'd0) | (r == 3'd4); cbit = r[2] ? 1'b0 : hold[~j]; end
      3'd2: begin cwr = r == 3'd1; cbit = hold[~j]; end
      3'd3: begin cwr = r == 3'd2; cbit = hold[~j]; end
      3'd4: begin
        cwr = r >= 3'd3;
        case (r)
          3'd3:    cbit = (j < 3'd3) ? hold[~j] :
                          (j == 3'd3) ? hit_ch[0] : (j == 3'd4) ? hit_ch[1] :
                          (j == 3'd5) ? hit_ch[2] : 1'b0;
          3'd4:    cbit = hold[{1'b0, j[1:0]} + 3'd1];         // env = 17 x level
          3'd5:    cbit = 1'b1;                                // aux = 255
          default: cbit = (t[3:0] == 4'd14) ? ~hold[0] :       // phase 0x4000 or 0x8000
                          (t[3:0] == 4'd15) ? hold[0] : 1'b0;
        endcase
      end
      default: ;
    endcase
  end

  always @(*) begin
    if (clearing)            tail = 1'b0;
    else if (con && cwr)     tail = cbit;
    else if (r == 3'd4)      tail = !kill && (c_dec ? sub_out : head);
    else if (r == 3'd5)      tail = c_adec ? sub_out : head;
    else if (t[5:4] == 2'b11) tail = ph_new;
    else                     tail = head;
  end

  // ------------------------------------------------------------ voice choice
  // On the last clock of a frame, voice u's bit b is ring[NL-2-u*L-b].
  wire [7:0] e0, e1;
  wire [2:0] h0, h1;
  genvar gk;
  generate
    for (gk = 0; gk < 8; gk = gk + 1) begin : g_e
      assign e0[gk] = ring[NL-2-32-gk];
      assign e1[gk] = ring[NL-2-L-32-gk];
    end
    for (gk = 0; gk < 3; gk = gk + 1) begin : g_h
      assign h0[gk] = ring[NL-2-27-gk];
      assign h1[gk] = ring[NL-2-L-27-gk];
    end
  endgenerate

  wire [2:0] hg   = (hit_ch == 3'd7) ? 3'd6 : hit_ch;
  wire       act0 = |e0, act1 = |e1;
  wire       same0 = act0 && ((h0 == 3'd7) ? 3'd6 : h0) == hg;
  wire       same1 = act1 && ((h1 == 3'd7) ? 3'd6 : h1) == hg;
  always @(*) begin
    if (same0)      choice = 1'b0;
    else if (same1) choice = 1'b1;
    else if (!act0) choice = 1'b0;
    else if (!act1) choice = 1'b1;
    else            choice = e1[7:5] < e0[7:5];
  end

  // ------------------------------------------------------------ noise sources
  reg [16:0] lfsr;
  always @(posedge clk) begin
    if (!rst_n) begin
      lfsr <= 17'd1;
    end else if (fend) begin
      lfsr <= {lfsr[15:0], lfsr[16] ^ lfsr[13]};
    end
  end

  wire [2:0] pc4   = lfsr[0] + lfsr[1] + lfsr[2] + lfsr[3];
  wire [8:0] dark  = pc4[2] ? 9'h0FF : {~pc4[1], pc4[0], 7'd0};
  wire [8:0] white = lfsr[0] ? 9'h0FF : 9'h100;
  wire [8:0] brite = (lfsr[0] == lfsr[1]) ? 9'h000 : lfsr[0] ? 9'h0FF : 9'h100;
  wire [8:0] metal = (frame[1] ^ frame[3] ^ frame[4]) ? 9'h0FF : 9'h100;
  wire [8:0] noise = c_color == 2'd0 ? dark : c_color == 2'd1 ? white :
                     c_color == 2'd2 ? brite : metal;

  // ------------------------------------------------------------ voice output
  // On each clock of the window, the source is the noise or the tone, by a
  // fixed 8-clock pattern set by mix; the source's amplitude a gives
  // a >> 3 clocks of 8 x source, then a & 7 clocks of 1 x source.
  wire       sel_n = (&c_mix) | ({t[0], t[1], t[2]} < c_mix);
  wire [7:0] amp   = sel_n ? c_an : c_at;
  wire [5:0] qr    = {1'b0, amp[7:3]} + {3'b000, amp[2:0]};
  wire       w8    = t < {1'b0, amp[7:3]};
  wire       w1    = !w8 && t < qr;
  wire [8:0] src   = sel_n ? noise : c_tone;
  wire [8:0] x     = clearing ? 9'd0 :
                     w8 ? src :
                     w1 ? {{3{src[8]}}, src[8:3]} : 9'd0;

  // ------------------------------------------------- second-order sigma-delta
  // As on sd2 at 1/8 scale (model: dac2): y = v2 >= 0, fb = y ? +512 : -512,
  // v1 <= clamp(v1 + x - fb) (12 bits), v2 <= v2 + v1 - 2 fb (14 bits).
  reg  [11:0] sd_v1;
  reg  [13:0] sd_v2;
  wire        y     = ~sd_v2[13];
  wire [12:0] x_fb  = {{3{y}}, ~x[8], x};
  wire [12:0] s1    = {sd_v1[11], sd_v1} + x_fb;
  wire        ovf1  = s1[12] ^ s1[11];
  wire [11:0] v1_n  = ovf1 ? {s1[12], {11{~s1[12]}}} : s1[11:0];
  wire [13:0] v2_n  = sd_v2 + {{2{sd_v1[11]}}, sd_v1} + {{3{y}}, 1'b1, 10'd0};
  wire        sd_restart = !rst_n || (fend && !act0 && !act1);

  always @(posedge clk) begin
    if (sd_restart) begin
      sd_v1 <= 12'd0;
      sd_v2 <= {14{1'b1}};
    end else begin
      sd_v1 <= v1_n;
      sd_v2 <= v2_n;
    end
  end

  assign audio = y;

endmodule
