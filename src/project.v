/*
 * UDS v3: 8-channel drum synthesizer with a full patch per HIT.
 * Copyright (c) 2026 Juris Vitols
 * SPDX-License-Identifier: Apache-2.0
 *
 * uo_out[6:0]  7-segment digit of the channel last hit
 * uo_out[7]    audio (second-order sigma-delta bitstream, low-pass filter it)
 * uio[0] CS_N in, uio[1] MOSI in, uio[2] MISO out, uio[3] SCK in
 * uio[4] FRAME out (high during voice window 0), uio[5] BUSY out
 * uio[6] audio out (left), uio[7] audio out (right): same signal, the chip is mono
 */
`default_nettype none

module tt_um_ai_wrangler_uds3 (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

  wire       miso, hit_cmd, stop, byte_done, audio, busy, frame_sync;
  wire [2:0] hit_ch, byte_idx;
  wire [7:0] hold;

  uds3_spi #(
      .CHIP_ID    (8'hD5),
      .VERSION_REG(8'h32)            // 3 = v3, 2 voices
  ) spi (
      .clk      (clk),
      .rst_n    (rst_n),
      .cs_n_pin (uio_in[0]),
      .sck_pin  (uio_in[3]),
      .mosi_pin (uio_in[1]),
      .miso     (miso),
      .hit_cmd  (hit_cmd),
      .stop     (stop),
      .ch       (hit_ch),
      .byte_done(byte_done),
      .idx      (byte_idx),
      .rx       (hold)
  );

  uds3_core core (
      .clk       (clk),
      .rst_n     (rst_n),
      .hit_cmd   (hit_cmd),
      .stop      (stop),
      .hit_ch    (hit_ch),
      .byte_done (byte_done),
      .byte_idx  (byte_idx),
      .hold      (hold),
      .audio     (audio),
      .busy      (busy),
      .frame_sync(frame_sync)
  );

  reg [6:0] digit;
  always @(*) begin
    case (hit_ch)
      3'd0:    digit = 7'h3F;
      3'd1:    digit = 7'h06;
      3'd2:    digit = 7'h5B;
      3'd3:    digit = 7'h4F;
      3'd4:    digit = 7'h66;
      3'd5:    digit = 7'h6D;
      3'd6:    digit = 7'h7D;
      default: digit = 7'h07;
    endcase
  end

  assign uo_out  = {audio, digit};
  assign uio_out = {audio, audio, busy, frame_sync, 1'b0, miso, 2'b00};
  assign uio_oe  = 8'b1111_0100;

  wire _unused = &{ena, ui_in, uio_in[7:4], uio_in[2], 1'b0};

endmodule
