"""CC1101 register definitions per datasheet (SWRS061I)."""

from enum import IntEnum

# ---------------------------------------------------------------------------
# SPI header byte constants
# ---------------------------------------------------------------------------
READ_SINGLE  = 0x80  # R/W=1, Burst=0
READ_BURST   = 0xC0  # R/W=1, Burst=1
WRITE_SINGLE = 0x00  # R/W=0, Burst=0
WRITE_BURST  = 0x40  # R/W=0, Burst=1

# FIFO access address (used with burst bit)
FIFO_ADDR = 0x3F

# ---------------------------------------------------------------------------
# Configuration registers  (0x00 – 0x2E)
# ---------------------------------------------------------------------------
class ConfigReg(IntEnum):
    IOCFG2   = 0x00  # GDO2 output pin configuration
    IOCFG1   = 0x01  # GDO1 output pin configuration
    IOCFG0   = 0x02  # GDO0 output pin configuration
    FIFOTHR  = 0x03  # RX FIFO and TX FIFO thresholds
    SYNC1    = 0x04  # Sync word, high byte
    SYNC0    = 0x05  # Sync word, low byte
    PKTLEN   = 0x06  # Packet length
    PKTCTRL1 = 0x07  # Packet automation control
    PKTCTRL0 = 0x08  # Packet automation control
    ADDR     = 0x09  # Device address
    CHANNR   = 0x0A  # Channel number
    FSCTRL1  = 0x0B  # Frequency synthesizer control
    FSCTRL0  = 0x0C  # Frequency synthesizer control
    FREQ2    = 0x0D  # Frequency control word, high byte
    FREQ1    = 0x0E  # Frequency control word, middle byte
    FREQ0    = 0x0F  # Frequency control word, low byte
    MDMCFG4  = 0x10  # Modem configuration
    MDMCFG3  = 0x11  # Modem configuration
    MDMCFG2  = 0x12  # Modem configuration
    MDMCFG1  = 0x13  # Modem configuration
    MDMCFG0  = 0x14  # Modem configuration
    DEVIATN  = 0x15  # Modem deviation setting
    MCSM2    = 0x16  # Main radio control state machine configuration
    MCSM1    = 0x17  # Main radio control state machine configuration
    MCSM0    = 0x18  # Main radio control state machine configuration
    FOCCFG   = 0x19  # Frequency offset compensation configuration
    BSCFG    = 0x1A  # Bit synchronisation configuration
    AGCCTRL2 = 0x1B  # AGC control
    AGCCTRL1 = 0x1C  # AGC control
    AGCCTRL0 = 0x1D  # AGC control
    WOREVT1  = 0x1E  # High byte Event 0 timeout
    WOREVT0  = 0x1F  # Low byte Event 0 timeout
    WORCTRL  = 0x20  # Wake on radio control
    FREND1   = 0x21  # Front end RX configuration
    FREND0   = 0x22  # Front end TX configuration
    FSCAL3   = 0x23  # Frequency synthesizer calibration
    FSCAL2   = 0x24  # Frequency synthesizer calibration
    FSCAL1   = 0x25  # Frequency synthesizer calibration
    FSCAL0   = 0x26  # Frequency synthesizer calibration
    RCCTRL1  = 0x27  # RC oscillator configuration
    RCCTRL0  = 0x28  # RC oscillator configuration
    FSTEST   = 0x29  # Frequency synthesizer calibration control
    PTEST    = 0x2A  # Production test
    AGCTEST  = 0x2B  # AGC test
    TEST2    = 0x2C  # Various test settings
    TEST1    = 0x2D  # Various test settings
    TEST0    = 0x2E  # Various test settings


# ---------------------------------------------------------------------------
# Status registers  (read-only, 0x30 – 0x3D, accessed via burst read)
# ---------------------------------------------------------------------------
class StatusReg(IntEnum):
    PARTNUM        = 0x30  # Part number for CC1101
    VERSION        = 0x31  # Current version number
    FREQEST        = 0x32  # Frequency offset estimate from demodulator
    LQI            = 0x33  # Demodulator estimate for link quality
    RSSI           = 0x34  # Received signal strength indication
    MARCSTATE      = 0x35  # Main radio control state machine state
    WORTIME1       = 0x36  # High byte of WOR time
    WORTIME0       = 0x37  # Low byte of WOR time
    PKTSTATUS      = 0x38  # Current GDOx status and packet status
    VCO_VC_DAC    = 0x39  # Current setting from PLL calibration module
    TXBYTES        = 0x3A  # Underflow and number of bytes in the TX FIFO
    RXBYTES        = 0x3B  # Overflow and number of bytes in the RX FIFO
    RCCTRL1_STATUS = 0x3C  # Last RC oscillator calibration result
    RCCTRL0_STATUS = 0x3D  # Last RC oscillator calibration result


# ---------------------------------------------------------------------------
# Command strobes  (0x30 – 0x3D, distinguished by single write without burst)
# ---------------------------------------------------------------------------
class Strobe(IntEnum):
    SRES  = 0x30  # Reset chip
    SFSTXON = 0x31  # Enable and calibrate frequency synthesizer
    SXOFF = 0x32  # Turn off crystal oscillator
    SCAL  = 0x33  # Calibrate frequency synthesizer and turn it off
    SRX   = 0x34  # Enable RX
    STX   = 0x35  # In IDLE state: enable TX
    SIDLE = 0x36  # Exit RX / TX, turn off frequency synthesizer
    SAFC  = 0x37  # Perform AFC adjustment
    SWOR  = 0x38  # Start automatic RX polling sequence
    SPWD  = 0x39  # Enter power down mode when CSn goes high
    SFRX  = 0x3A  # Flush the RX FIFO buffer
    SFTX  = 0x3B  # Flush the TX FIFO buffer
    SWORRST = 0x3C  # Reset real time clock to Event1 value
    SNOP  = 0x3D  # No operation


# ---------------------------------------------------------------------------
# Modulation format values (MDMCFG2[5:4])
# ---------------------------------------------------------------------------
MOD_2FSK  = 0x00
MOD_GFSK  = 0x10
MOD_ASK   = 0x30  # OOK / ASK
MOD_4FSK  = 0x40
MOD_MSK   = 0x70

# ---------------------------------------------------------------------------
# MARCSTATE values
# ---------------------------------------------------------------------------
class MarcState(IntEnum):
    SLEEP        = 0x00
    IDLE         = 0x01
    XOFF         = 0x02
    VCOON_MC     = 0x03
    REGON_MC     = 0x04
    MANCAL       = 0x05
    VCOON        = 0x06
    REGON        = 0x07
    STARTCAL     = 0x08
    BWBOOST      = 0x09
    FS_LOCK      = 0x0A
    IFADCON      = 0x0B
    ENDCAL       = 0x0C
    RX           = 0x0D
    RX_END       = 0x0E
    RX_RST       = 0x0F
    TXRX_SWITCH  = 0x10
    RXFIFO_OVERFLOW = 0x11
    FSTXON       = 0x12
    TX           = 0x13
    TX_END       = 0x14
    RXTX_SWITCH  = 0x15
    TXFIFO_UNDERFLOW = 0x16

# ---------------------------------------------------------------------------
# Packet control constants
# ---------------------------------------------------------------------------
PKTCTRL0_FIXED_LENGTH    = 0x00  # Fixed packet length mode
PKTCTRL0_VARIABLE_LENGTH = 0x01  # Variable packet length mode
PKTCTRL0_INFINITE_LENGTH  = 0x02  # Infinite packet length mode
PKTCTRL0_WHITENING       = 0x40  # Data whitening on

# ---------------------------------------------------------------------------
# Crystal frequency and commonly used sync word
# ---------------------------------------------------------------------------
XTAL_FREQ_HZ = 26_000_000

SYNC_WORD_DEFAULT = 0xD391
SYNC_WORD_TADO = 0x91D3
