import time
import random
import math

class PlantSimulator:
    def __init__(self):
        # Operational Setpoints
        self.pump_rpm = 1500.0        # Range: 0 to 3000 RPM
        self.valve_v101_open = 100.0  # Inlet valve open % (0 to 100)
        self.valve_v102_open = 100.0  # Outlet valve open % (0 to 100)
        self.drain_valve_open = 50.0  # Product drain valve % (0 to 100)
        
        # Tank levels
        self.level_t101 = 85.0        # Source Tank level % (0 to 100, max 200L)
        self.level_t102 = 15.0        # Product Tank level % (0 to 100, max 200L)
        
        # Active Fault: "NORMAL", "PUMP_CAVITATION", "PIPE_LEAK", "VALVE_CLOG"
        self.active_fault = "NORMAL"
        
        # Internal variables for smooth transitions
        self.motor_temp = 25.0
        self.motor_vibration = 0.6
        self.replenish_flow = 8.0     # Constant water inflow to T-101 (L/min)
        
        # CMDB & Health Analytics tracking
        self.pump_health_index = 100.0
        self.cumulative_runtime = 0.0  # seconds
        self.alarm_acknowledged = True
        self.remaining_useful_life = "365.0 days"
        
        # Last updated time
        self.last_update = time.time()

    def set_controls(self, pump_rpm=None, v101=None, v102=None, drain=None):
        if pump_rpm is not None:
            self.pump_rpm = max(0.0, min(3000.0, float(pump_rpm)))
        if v101 is not None:
            self.valve_v101_open = max(0.0, min(100.0, float(v101)))
        if v102 is not None:
            self.valve_v102_open = max(0.0, min(100.0, float(v102)))
        if drain is not None:
            self.drain_valve_open = max(0.0, min(100.0, float(drain)))

    def trigger_fault(self, fault_type):
        valid_faults = ["NORMAL", "PUMP_CAVITATION", "PIPE_LEAK", "VALVE_CLOG"]
        if fault_type in valid_faults:
            self.active_fault = fault_type
            self.alarm_acknowledged = (fault_type == "NORMAL")
            print(f"Simulator: Fault set to {fault_type}, Acknowledge flag: {self.alarm_acknowledged}")
            return True
        return False

    def update(self):
        """Simulates 1 second of physical state transition."""
        now = time.time()
        dt = now - self.last_update
        self.last_update = now
        
        # Clamp dt to reasonable bounds in case of lag
        dt = min(2.0, max(0.1, dt))
        
        # --- Physics Equations ---
        rpm_ratio = self.pump_rpm / 3000.0
        
        # Accumulate runtime (degradation calculated post-physics)
        if self.pump_rpm > 100:
            self.cumulative_runtime += dt
            
        # Normal calculations
        v101_ratio = self.valve_v101_open / 100.0
        v102_ratio = self.valve_v102_open / 100.0
        
        # Calculate Flow Rate entering the pump (suction flow)
        suction_flow = rpm_ratio * 24.0 * v101_ratio
        
        # Calculate normal pressure and flows
        if self.pump_rpm > 100:
            normal_flow = suction_flow * v102_ratio
            normal_pressure = 10.0 + (rpm_ratio * 25.0) * (2.0 - v102_ratio) + random.uniform(-0.3, 0.3)
        else:
            normal_flow = 0.0
            normal_pressure = 0.0
            
        # Default physical variables
        fit101_flow = normal_flow       # Flow right after pump
        fit102_flow = normal_flow       # Flow after filter (inlet to T-102)
        pit101_pressure = normal_pressure # Pressure before filter
        current_draw = 0.5 + (rpm_ratio * 4.0) + (pit101_pressure * 0.08) # Amps
        
        # Noise
        noise_flow = random.uniform(-0.1, 0.1) if self.pump_rpm > 100 else 0
        noise_press = random.uniform(-0.2, 0.2) if self.pump_rpm > 100 else 0
        noise_vib = random.uniform(-0.05, 0.05) if self.pump_rpm > 100 else random.uniform(0, 0.02)
        
        target_vibration = 0.5 + (rpm_ratio * 0.8) + noise_vib
        target_temp = 24.0 + (rpm_ratio * 22.0) + (current_draw * 2.5)
        
        # --- Inject Fault Conditions ---
        
        if self.active_fault == "PUMP_CAVITATION":
            # Pump Cavitation occurs typically when suction is starved (v101 is closed or blocked)
            # Or simulated as an active cavitation state
            fit101_flow = normal_flow * 0.15 + random.uniform(-0.3, 0.3) # major drop in flow
            fit102_flow = fit101_flow
            pit101_pressure = normal_pressure * 0.2 + random.uniform(-0.5, 0.5) # pressure loss
            
            # Vibration spikes dramatically and erratically
            target_vibration = 7.8 + (rpm_ratio * 4.5) + random.uniform(-1.5, 1.5)
            # Current fluctuates erratically
            current_draw = 1.5 + (rpm_ratio * 1.5) + math.sin(time.time() * 5.0) * 0.6 + random.uniform(-0.2, 0.2)
            # Temperature climbs fast because there is no water to cool the pump
            target_temp = 68.0 + (rpm_ratio * 18.0) + random.uniform(-1.0, 1.0)
            
        elif self.active_fault == "PIPE_LEAK":
            # Pipe leak between pump (FIT101) and filter (FIT102)
            # Flow leaving pump is high, flow entering filter/T-102 is low
            fit101_flow = normal_flow * 1.1 + random.uniform(-0.2, 0.2) # High discharge flow
            fit102_flow = normal_flow * 0.35 + random.uniform(-0.1, 0.1) # low flow at destination
            pit101_pressure = normal_pressure * 0.4 + random.uniform(-0.4, 0.4) # pressure drop
            # Vibration increases slightly due to uneven backpressure
            target_vibration = 1.8 + (rpm_ratio * 0.5) + random.uniform(-0.1, 0.1)
            target_temp = 24.0 + (rpm_ratio * 18.0)
            
        elif self.active_fault == "VALVE_CLOG":
            # Valve V-102 or filter is severely clogged
            # Flow drops, pressure before filter spikes dramatically
            fit101_flow = normal_flow * 0.08 + random.uniform(-0.05, 0.05)
            fit102_flow = fit101_flow
            
            # Deadhead pressure spikes
            pit101_pressure = 58.0 + (rpm_ratio * 12.0) + random.uniform(-0.8, 0.8)
            # Current spikes due to high workload
            current_draw = 1.0 + (rpm_ratio * 5.0) + (pit101_pressure * 0.12)
            # Vibration increases due to back-pressure turbulence
            target_vibration = 2.4 + (rpm_ratio * 1.2) + random.uniform(-0.2, 0.2)
            target_temp = 48.0 + (rpm_ratio * 20.0)

        # Clamping outputs to physically possible ranges
        fit101_flow = max(0.0, fit101_flow + noise_flow)
        fit102_flow = max(0.0, fit102_flow + noise_flow)
        pit101_pressure = max(0.0, pit101_pressure + noise_press)
        current_draw = max(0.1, current_draw)
        
        # Smooth temperature and vibration integration
        temp_k = 0.05 * dt # thermal inertia
        self.motor_temp += (target_temp - self.motor_temp) * temp_k
        
        vib_k = 0.3 * dt
        self.motor_vibration += (target_vibration - self.motor_vibration) * vib_k
        self.motor_vibration = max(0.1, self.motor_vibration)
        self.motor_vibration = max(0.1, self.motor_vibration)

        # Accumulate runtime and calculate degradation
        degradation_rate = 0.0
        if self.pump_rpm > 100:
            # Base normal wear-and-tear degradation
            degradation_rate = 0.0005
            
            # 1. Thermal stress multiplier
            if self.motor_temp > 50.0:
                degradation_rate += (self.motor_temp - 50.0) * 0.0002
                
            # 2. Overcurrent fatigue multiplier
            if current_draw > 5.0:
                degradation_rate += (current_draw - 5.0) * 0.002
                
            # 3. Vibration shock multiplier
            degradation_rate += (self.motor_vibration ** 2) * 0.0001
            
            # Accelerated degradation under faults
            if self.active_fault == "PUMP_CAVITATION":
                degradation_rate += 0.08
            elif self.active_fault == "VALVE_CLOG":
                degradation_rate += 0.02
            elif self.active_fault == "PIPE_LEAK":
                degradation_rate += 0.005
                
            self.pump_health_index -= degradation_rate * rpm_ratio * dt
            self.pump_health_index = max(0.0, min(100.0, self.pump_health_index))
            
        # 4. Predict Remaining Useful Life (RUL)
        total_deg_per_sec = degradation_rate * rpm_ratio
        if total_deg_per_sec > 0 and self.pump_health_index > 0:
            seconds_remaining = self.pump_health_index / total_deg_per_sec
            if seconds_remaining > 86400:
                self.remaining_useful_life = f"{round(seconds_remaining / 86400.0, 1)} days"
            elif seconds_remaining > 3600:
                self.remaining_useful_life = f"{int(seconds_remaining / 3600)} hours"
            elif seconds_remaining > 60:
                self.remaining_useful_life = f"{int(seconds_remaining / 60)} minutes"
            else:
                self.remaining_useful_life = f"{int(seconds_remaining)} seconds"
        else:
            self.remaining_useful_life = "365.0 days"

        # --- Tank Level Integration (Liters/Min to Liters, 1 sec = dt/60 min)
        # Tank capacities: 200 Liters each
        # LIT levels are in % (volume / 200 * 100)
        
        t101_volume = (self.level_t101 / 100.0) * 200.0
        t102_volume = (self.level_t102 / 100.0) * 200.0
        
        # Source tank: Replenish in, and flow out (using flow after pump FIT101)
        # In leak mode, T-101 drains at the speed of fit101_flow
        drain_rate_t101 = fit101_flow
        t101_volume += (self.replenish_flow - drain_rate_t101) * (dt / 60.0)
        
        # Product tank: Flow in (fit102_flow) and drain out
        drain_flow_t102 = (self.drain_valve_open / 100.0) * 12.0 # Max drain 12 L/min
        t102_volume += (fit102_flow - drain_flow_t102) * (dt / 60.0)
        
        # Keep volumes in bounds [0, 200]
        t101_volume = max(0.0, min(200.0, t101_volume))
        t102_volume = max(0.0, min(200.0, t102_volume))
        
        self.level_t101 = (t101_volume / 200.0) * 100.0
        self.level_t102 = (t102_volume / 200.0) * 100.0
        
        equipment_utilization = (self.pump_rpm / 3000.0) * 100.0
        
        return {
            "pump_rpm": round(self.pump_rpm, 1),
            "valve_v101_open": round(self.valve_v101_open, 1),
            "valve_v102_open": round(self.valve_v102_open, 1),
            "drain_valve_open": round(self.drain_valve_open, 1),
            "level_t101": round(self.level_t101, 1),
            "level_t102": round(self.level_t102, 1),
            "flow_fit101": round(fit101_flow, 2),
            "flow_fit102": round(fit102_flow, 2),
            "pressure_pit101": round(pit101_pressure, 2),
            "motor_temp": round(self.motor_temp, 2),
            "motor_vibration": round(self.motor_vibration, 2),
            "motor_current": round(current_draw, 2),
            "pump_health_index": round(self.pump_health_index, 2),
            "cumulative_runtime": round(self.cumulative_runtime, 1),
            "alarm_acknowledged": self.alarm_acknowledged,
            "active_fault": self.active_fault,
            "equipment_utilization": round(equipment_utilization, 2),
            "remaining_useful_life": self.remaining_useful_life,
            "timestamp": time.time()
        }

# Single global instance of simulator
simulator = PlantSimulator()
