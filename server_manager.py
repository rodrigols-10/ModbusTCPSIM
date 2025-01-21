# server_manager.py

from pyModbusTCP.server import ModbusServer

class ServerData:
    """
    Representa um servidor Modbus, contendo:
      - Porta utilizada
      - Número de coils
      - Número de registers
      - Objeto ModbusServer
      - Listas (coils e registers) para refletir o estado atual
    """

    def __init__(self, port, num_coils, num_registers):
        self.port = port
        self.num_coils = num_coils
        self.num_registers = num_registers

        # Servidor Modbus
        self.server_obj = ModbusServer(host="127.0.0.1", port=port, no_block=True)

        # Armazenamento local
        self.coils = [0] * num_coils
        self.registers = [0] * num_registers

    def start(self):
        """Inicia o servidor e configura os valores iniciais."""
        self.server_obj.start()
        # Inicializar data_bank do servidor
        self.server_obj.data_bank.set_coils(0, self.coils)
        self.server_obj.data_bank.set_holding_registers(0, self.registers)

    def stop(self):
        """Para o servidor."""
        self.server_obj.stop()

    def read_all(self):
        """Sincroniza (coils e registers) lendo os valores atuais do data_bank."""
        coils_data = self.server_obj.data_bank.get_coils(0, self.num_coils) or []
        if len(coils_data) == self.num_coils:
            self.coils = coils_data

        regs_data = self.server_obj.data_bank.get_holding_registers(0, self.num_registers) or []
        if len(regs_data) == self.num_registers:
            self.registers = regs_data

    def update_coil(self, index, value):
        """Atualiza coil no data_bank."""
        if 0 <= index < self.num_coils:
            val = 1 if value != 0 else 0
            self.coils[index] = val
            self.server_obj.data_bank.set_coils(index, [val])

    def update_register(self, index, value):
        """Atualiza register no data_bank."""
        if 0 <= index < self.num_registers:
            self.registers[index] = value
            self.server_obj.data_bank.set_holding_registers(index, [value])

    def set_all_zero(self):
        """Zera todos os coils e registers."""
        self.coils = [0] * self.num_coils
        self.registers = [0] * self.num_registers
        self.server_obj.data_bank.set_coils(0, self.coils)
        self.server_obj.data_bank.set_holding_registers(0, self.registers)

    def set_random_values(self):
        """
        Define valores aleatórios para todos os coils e registers:
        - Coils: 0 ou 1
        - Registers: 0..65535
        """
        import random
        for i in range(self.num_coils):
            val = random.randint(0, 1)
            self.update_coil(i, val)

        for i in range(self.num_registers):
            val = random.randint(0, 65535)
            self.update_register(i, val)
