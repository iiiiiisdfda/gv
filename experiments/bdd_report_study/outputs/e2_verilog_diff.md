# E2: Verilog input 宣告順序差異（excerpt）

## grep input（兩檔）

### -inputorder file
  input reset;
  input clk;

### -inputorder rdfs
  input reset;
  input clk;

## diff -u（input 行）

## 說明

- `basic/a.v` 僅兩個 PI（reset, clk），且 Yosys 寫出時可能與內部 PI 順序一致，故兩種 `-InputOrder` 的 `input` 行常相同。
- 多 PI、多行 `input` 宣告的設計較易觀察順序差異；讀回驗證可參考 `tests/cir/dofile/cirwrite_verilog_inputorder.dofile`。
