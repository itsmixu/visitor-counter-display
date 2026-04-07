from micropython import const
import framebuf

_REG_NOOP        = const(0x00)
_REG_DIGIT0      = const(0x01)
_REG_DECODEMODE  = const(0x09)
_REG_INTENSITY   = const(0x0A)
_REG_SCANLIMIT   = const(0x0B)
_REG_SHUTDOWN    = const(0x0C)
_REG_DISPLAYTEST = const(0x0F)

class Matrix8x8(framebuf.FrameBuffer):
    def __init__(self, spi, cs, num=1):
        self.spi = spi
        self.cs = cs
        self.num = num
        self.buffer = bytearray(8 * num)
        self.cs.init(self.cs.OUT, value=1)
        super().__init__(self.buffer, 8 * num, 8, framebuf.MONO_HLSB)
        self._init_display()

    def _write_all(self, register, data):
        self.cs.value(0)
        for _ in range(self.num):
            self.spi.write(bytearray([register, data]))
        self.cs.value(1)

    def _init_display(self):
        self._write_all(_REG_SHUTDOWN, 0)
        self._write_all(_REG_DECODEMODE, 0)
        self._write_all(_REG_DISPLAYTEST, 0)
        self._write_all(_REG_INTENSITY, 3)
        self._write_all(_REG_SCANLIMIT, 7)
        self._write_all(_REG_SHUTDOWN, 1)
        self.fill(0)
        self.show()

    def brightness(self, value):
        value = max(0, min(15, value))
        self._write_all(_REG_INTENSITY, value)

    def show(self):
        for row in range(8):
            self.cs.value(0)
            for m in range(self.num):
                self.spi.write(bytearray([_REG_DIGIT0 + row, self.buffer[row * self.num + m]]))
            self.cs.value(1)
