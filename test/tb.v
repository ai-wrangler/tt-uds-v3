`default_nettype none
`timescale 1ns / 1ps

/* Testbench for UDS v3. Besides the usual wiring it counts the 1s on the
   audio pin in every 64-clock window, so the cocotb test can compare each
   window with the Python model (model/uds3_model.py). cyc is the chip's own
   clock count since reset (it restarts the same way as the chip's counter).
*/
module tb ();

  initial begin
    $dumpfile("tb.fst");
    $dumpvars(1, tb);
    #1;
  end

  reg clk;
  reg rst_n;
  reg ena;
  reg [7:0] ui_in;
  reg [7:0] uio_in;
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;
`ifdef GL_TEST
  wire VPWR = 1'b1;
  wire VGND = 1'b0;
`endif

  tt_um_ai_wrangler_uds3 user_project (
`ifdef GL_TEST
      .VPWR(VPWR),
      .VGND(VGND),
`endif
      .ui_in  (ui_in),
      .uo_out (uo_out),
      .uio_in (uio_in),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (ena),
      .clk    (clk),
      .rst_n  (rst_n)
  );

  wire        audio = uo_out[7];
  reg  [31:0] cyc;
  reg  [6:0]  acc;
  reg  [6:0]  win_ones;     // 1s in the last complete window
  reg  [31:0] nwin;         // windows completed

  always @(posedge clk) begin
    if (!rst_n) begin
      cyc  <= 32'd0;
      acc  <= 7'd0;
      nwin <= 32'd0;
    end else begin
      if (cyc[5:0] == 6'd63) begin
        win_ones <= acc + {6'd0, audio};
        acc      <= 7'd0;
        nwin     <= nwin + 32'd1;
      end else begin
        acc <= acc + {6'd0, audio};
      end
      cyc <= cyc + 32'd1;
    end
  end

endmodule
