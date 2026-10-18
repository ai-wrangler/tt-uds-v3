/*
 * UDS v3: SPI receiver (mode 0, MSB first).
 *
 * Messages (CS low for the whole message):
 *   HIT   0x18|ch, P0, P1, P2, P3      (the patch; see docs/v3/CONTRACT.md)
 *   READ  0x30|reg, then one byte clocked out on MISO (reg 0 ID, reg 1 VERSION)
 *   STOP  0x40
 * SCK and CS are oversampled by clk. Each patch byte is handed to the voice
 * engine on its own (byte_done), and the engine writes it into the target
 * voice within about one frame. BUSY is high from the end of each HIT byte
 * until the engine has taken it: the host waits for BUSY low after every
 * byte of a HIT. Keep SCK at or below clk/6.
 *
 * SPDX-License-Identifier: Apache-2.0
 */
`default_nettype none

module uds3_spi #(
    parameter [7:0] CHIP_ID     = 8'hD5,
    parameter [7:0] VERSION_REG = 8'h32
) (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       cs_n_pin,
    input  wire       sck_pin,
    input  wire       mosi_pin,
    output wire       miso,

    output wire       hit_cmd,      // one-clock pulse: a HIT command byte arrived
    output wire       stop,         // one-clock pulse: STOP
    output reg  [2:0] ch,           // channel of the last HIT
    output wire       byte_done,    // one-clock pulse: patch byte P[idx-1] is in rx
    output wire [2:0] idx,          // 1..4: which patch byte rx has
    output reg  [7:0] rx            // stays until the next SCK edge (the host waits for BUSY)
);

  reg [1:0] cs_s;       // synchronizer; cs_s[1] is the CS level
  reg [2:0] sck_s;      // synchronizer; [1] is the SCK level, [2] the previous one
  reg       mosi_s;
  reg [2:0] bitcnt;
  reg [2:0] bytecnt;    // bytes done in this message, stops at 5
  reg       is_hit;

  wire       active   = !cs_s[1];
  wire       rise     = active && sck_s[1] && !sck_s[2];
  wire       last_bit = rise && bitcnt == 3'd7;
  wire [7:0] byte_in  = {rx[6:0], mosi_s};
  wire       cmd_end  = last_bit && bytecnt == 3'd0;

  assign hit_cmd   = cmd_end && byte_in[7:3] == 5'b00011;
  assign stop      = cmd_end && byte_in == 8'h40;
  assign byte_done = last_bit && is_hit && bytecnt != 3'd0 && bytecnt <= 3'd4;
  assign miso      = active & rx[7];

  always @(posedge clk) begin
    mosi_s <= mosi_pin;
    if (!rst_n) begin
      cs_s    <= 2'b11;
      sck_s   <= 3'b000;
      bitcnt  <= 3'd0;
      bytecnt <= 3'd0;
      is_hit  <= 1'b0;
      ch      <= 3'd0;
    end else begin
      cs_s  <= {cs_s[0], cs_n_pin};
      sck_s <= {sck_s[1:0], sck_pin};
      if (!active) begin
        bitcnt  <= 3'd0;
        bytecnt <= 3'd0;
        is_hit  <= 1'b0;
      end else if (rise) begin
        bitcnt <= bitcnt + 3'd1;
        if (last_bit && bytecnt != 3'd5) bytecnt <= bytecnt + 3'd1;
      end
      if (hit_cmd) begin
        is_hit <= 1'b1;
        ch     <= byte_in[2:0];
      end
    end
  end

  assign idx = bytecnt;

  // receive register; a READ answer goes out on the next byte
  always @(posedge clk) begin
    if (rise) begin
      if (cmd_end && byte_in[7:4] == 4'h3)
        rx <= (byte_in[3:0] == 4'd0) ? CHIP_ID : (byte_in[3:0] == 4'd1) ? VERSION_REG : 8'h00;
      else
        rx <= byte_in;
    end
  end

endmodule
