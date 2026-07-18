import os
import random
import time
from app.services.simulator.simulator import simulator

class OPCUAClient:
    def __init__(self, endpoint_url="opc.tcp://192.168.1.50:4840"):
        self.endpoint_url = endpoint_url
        self.connected = False

    def connect(self):
        self.connected = True
        print(f"OPC-UA: Connected to PLC endpoint {self.endpoint_url}")

    def read_node(self, node_id):
        if not self.connected:
            self.connect()
        if "BoosterPump.RPM" in node_id:
            return 1500.0 + random.uniform(-10.0, 10.0)
        elif "BoosterPump.Vibration" in node_id:
            return 0.75 + random.uniform(-0.05, 0.05)
        elif "BoosterPump.Temperature" in node_id:
            return 32.5 + random.uniform(-0.2, 0.2)
        elif "WaterSystem.FIT101" in node_id:
            return 12.0 + random.uniform(-0.1, 0.1)
        elif "WaterSystem.FIT102" in node_id:
            return 11.95 + random.uniform(-0.1, 0.1)
        elif "WaterSystem.PIT101" in node_id:
            return 22.4 + random.uniform(-0.3, 0.3)
        elif "BoosterPump.Current" in node_id:
            return 4.2 + random.uniform(-0.05, 0.05)
        return 0.0

    def write_node(self, node_id, value):
        if not self.connected:
            self.connect()
        print(f"OPC-UA: Wrote value {value} to Node ID: {node_id}")
        return True

    def fetch_telemetry(self) -> dict:
        return {
            "pump_rpm": round(self.read_node("ns=2;s=BoosterPump.RPM"), 1),
            "motor_vibration": round(self.read_node("ns=2;s=BoosterPump.Vibration"), 3),
            "motor_temp": round(self.read_node("ns=2;s=BoosterPump.Temperature"), 2),
            "flow_fit101": round(self.read_node("ns=2;s=WaterSystem.FIT101"), 2),
            "flow_fit102": round(self.read_node("ns=2;s=WaterSystem.FIT102"), 2),
            "pressure_pit101": round(self.read_node("ns=2;s=WaterSystem.PIT101"), 2),
            "motor_current": round(self.read_node("ns=2;s=BoosterPump.Current"), 2),
            "level_t101": 84.5,
            "level_t102": 15.5,
            "pump_health_index": 98.5,
            "remaining_useful_life": "342.0 days",
            "active_fault": "NORMAL"
        }


class ModbusTCPClient:
    def __init__(self, ip="192.168.1.100", port=502):
        self.ip = ip
        self.port = port
        self.connected = False

    def connect(self):
        self.connected = True
        print(f"Modbus TCP: Connected to device {self.ip}:{self.port}")

    def read_input_registers(self, address, count):
        if not self.connected:
            self.connect()
        mock_values = {
            30001: 1495,
            30002: 82,
            30003: 3180,
            30004: 1192,
            30005: 1188,
            30006: 2215,
            30007: 415
        }
        res = []
        for addr in range(address, address + count):
            res.append(mock_values.get(addr, 0))
        return res

    def write_holding_register(self, address, value):
        if not self.connected:
            self.connect()
        print(f"Modbus TCP: Wrote register {address} value {value}")
        return True

    def fetch_telemetry(self) -> dict:
        regs = self.read_input_registers(30001, 7)
        return {
            "pump_rpm": float(regs[0]),
            "motor_vibration": round(float(regs[1]) / 100.0, 3),
            "motor_temp": round(float(regs[2]) / 100.0, 2),
            "flow_fit101": round(float(regs[3]) / 100.0, 2),
            "flow_fit102": round(float(regs[4]) / 100.0, 2),
            "pressure_pit101": round(float(regs[5]) / 100.0, 2),
            "motor_current": round(float(regs[6]) / 100.0, 2),
            "level_t101": 84.1,
            "level_t102": 15.9,
            "pump_health_index": 98.1,
            "remaining_useful_life": "339.0 days",
            "active_fault": "NORMAL"
        }


class DataAcquisitionService:
    def __init__(self, simulator_inst):
        self.simulator = simulator_inst
        self.mode = "SIMULATOR"
        self.opc_client = OPCUAClient()
        self.modbus_client = ModbusTCPClient()
        self.external_telemetry = None

    def set_mode(self, mode: str):
        valid_modes = ["SIMULATOR", "OPC-UA", "MODBUS", "MQTT", "REST"]
        if mode in valid_modes:
            self.mode = mode
            print(f"DAQ Service: Protocol mode switched to {self.mode}")
            return True
        return False

    def ingest_rest_telemetry(self, telemetry: dict):
        self.external_telemetry = telemetry
        print("DAQ Service: Telemetry ingested via REST input API.")

    def fetch(self) -> dict:
        if self.mode == "SIMULATOR":
            return self.simulator.update()
        elif self.mode == "OPC-UA":
            return self.opc_client.fetch_telemetry()
        elif self.mode == "MODBUS":
            return self.modbus_client.fetch_telemetry()
        elif self.mode == "REST" or self.mode == "MQTT":
            if self.external_telemetry:
                return self.external_telemetry
            return self.simulator.update()
        return self.simulator.update()

    def dispatch_control(self, pump_rpm=None, v101=None, v102=None, drain=None):
        print(f"DAQ Service: Dispatching control command down-link via {self.mode}")
        if self.mode == "SIMULATOR":
            self.simulator.set_controls(pump_rpm, v101, v102, drain)
        elif self.mode == "OPC-UA":
            if pump_rpm is not None:
                self.opc_client.write_node("ns=2;s=BoosterPump.RPM_Setpoint", pump_rpm)
            if v101 is not None:
                self.opc_client.write_node("ns=2;s=WaterSystem.V101_Command", v101)
        elif self.mode == "MODBUS":
            if pump_rpm is not None:
                self.modbus_client.write_holding_register(40001, int(pump_rpm))
            if v101 is not None:
                self.modbus_client.write_holding_register(40002, int(v101))

# Instantiate singleton service
daq_service = DataAcquisitionService(simulator)
