import { Injectable, signal, computed, effect } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { interval, Subscription, BehaviorSubject } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';

export interface Telemetry {
  pump_rpm: number;
  valve_v101_open: number;
  valve_v102_open: number;
  drain_valve_open: number;
  level_t101: number;
  level_t102: number;
  flow_fit101: number;
  flow_fit102: number;
  pressure_pit101: number;
  motor_temp: number;
  motor_vibration: number;
  motor_current: number;
  pump_health_index: number;
  cumulative_runtime: number;
  alarm_acknowledged: boolean;
  active_fault: string;
  equipment_utilization?: number;
  timestamp: number;
}

export interface AIAnalysis {
  classification: string;
  anomaly_score: number;
  confidence: number;
  reconstruction_error: number;
  capacity_status?: string;
  capacity_utilization?: number;
  capacity_message?: string;
}

export interface LiveData {
  telemetry: Telemetry;
  ai_analysis: AIAnalysis;
}

export interface CopilotPlan {
  fault_type: string;
  rca: string;
  mitigation: string;
  plc_code: string;
  dtdl_patch: any;
}

export interface WorkOrderResponse {
  status: string;
  ticket_id: string;
  timestamp: number;
  azure_devops_url: string;
  message: string;
}

export interface SettingsData {
  normal_flow_setpoint?: number;
  max_pressure_threshold?: number;
  target_water_level?: number;
  twilio_sid?: string;
  twilio_token?: string;
  twilio_from?: string;
  operator_phone?: string;
  polling_rate?: number;
}

export interface FaultRecord {
  type: string;
  description: string;
  active: boolean;
  status: string;
  timestamp: string;
}

export interface NotificationRecord {
  type: string;
  destination: string;
  message: string;
  status: string;
  timestamp: string;
}

@Injectable({
  providedIn: 'root'
})
export class TelemetryService {
  private apiUrl = 'http://localhost:8000';
  private pollingSub: Subscription | null = null;

  // Signals for components
  readonly liveData = signal<LiveData | null>(null);
  readonly telemetryHistory = signal<Telemetry[]>([]);
  readonly activeFault = computed(() => this.liveData()?.telemetry.active_fault || 'NORMAL');
  readonly aiAnalysis = computed(() => this.liveData()?.ai_analysis || null);
  readonly isPolling = signal<boolean>(false);
  readonly copilotPlan = signal<CopilotPlan | null>(null);
  readonly connectionError = signal<string | null>(null);

  constructor(private http: HttpClient) {
    // Automatically load history when starting
    this.loadHistory();
    this.startPolling();

    // Automatically load copilot plan when active fault changes
    effect(() => {
      const fault = this.activeFault();
      this.loadCopilotPlan();
    });
  }

  startPolling(rateMs: number = 1000) {
    if (this.pollingSub) {
      this.pollingSub.unsubscribe();
    }
    this.isPolling.set(true);
    this.pollingSub = interval(rateMs)
      .pipe(
        switchMap(() => this.http.get<LiveData>(`${this.apiUrl}/api/telemetry/live`)),
        catchError(err => {
          console.error('API Poll error:', err);
          this.connectionError.set('Lost connection to AetherTwin Backend. Please ensure backend is running.');
          // Return an empty/null observable on error to keep the interval going
          throw err;
        })
      )
      .subscribe({
        next: (data) => {
          this.liveData.set(data);
          this.connectionError.set(null);
          
          // Append to rolling history log locally
          const hist = [...this.telemetryHistory(), data.telemetry];
          if (hist.length > 50) {
            hist.shift();
          }
          this.telemetryHistory.set(hist);
        },
        error: (err) => {
          this.isPolling.set(false);
        }
      });
  }

  stopPolling() {
    if (this.pollingSub) {
      this.pollingSub.unsubscribe();
      this.pollingSub = null;
    }
    this.isPolling.set(false);
  }

  loadHistory() {
    this.http.get<Telemetry[]>(`${this.apiUrl}/api/telemetry/history?limit=50`).subscribe({
      next: (data) => this.telemetryHistory.set(data),
      error: (err) => console.error('Error fetching history:', err)
    });
  }

  updateControls(controls: { pump_rpm?: number; valve_v101_open?: number; valve_v102_open?: number; drain_valve_open?: number }) {
    // Map control names to backend body expected keys
    const body = {
      pump_rpm: controls.pump_rpm,
      valve_v101_open: controls.valve_v101_open,
      valve_v102_open: controls.valve_v102_open,
      drain_valve_open: controls.drain_valve_open
    };
    return this.http.post<any>(`${this.apiUrl}/api/controls`, body).subscribe({
      next: (res) => {
        if (res.current_state) {
          const currentLive = this.liveData();
          if (currentLive) {
            this.liveData.set({
              ...currentLive,
              telemetry: res.current_state
            });
          }
        }
      },
      error: (err) => console.error('Error updating controls:', err)
    });
  }

  triggerFault(faultType: string) {
    return this.http.post<any>(`${this.apiUrl}/api/fault/trigger`, { fault_type: faultType }).subscribe({
      next: () => {
        this.loadCopilotPlan();
      },
      error: (err) => console.error('Error triggering fault:', err)
    });
  }

  applyMitigation() {
    return this.http.post<any>(`${this.apiUrl}/api/fault/mitigate`, {}).subscribe({
      next: (res) => {
        // Reload live data immediately
        if (res.new_state) {
          const currentLive = this.liveData();
          if (currentLive) {
            this.liveData.set({
              ...currentLive,
              telemetry: res.new_state
            });
          }
        }
        this.loadCopilotPlan();
      },
      error: (err) => console.error('Error applying mitigation:', err)
    });
  }

  loadCopilotPlan() {
    this.http.get<CopilotPlan>(`${this.apiUrl}/api/copilot/plan`).subscribe({
      next: (plan) => this.copilotPlan.set(plan),
      error: (err) => console.error('Error loading copilot plan:', err)
    });
  }

  getDtdl() {
    return this.http.get<any[]>(`${this.apiUrl}/api/azure/dtdl`);
  }

  createWorkOrder(wo: { component_id: string; fault_type: string; priority: string; description: string }) {
    return this.http.post<WorkOrderResponse>(`${this.apiUrl}/api/work-order/create`, wo);
  }

  getAssets() {
    return this.http.get<any[]>(`${this.apiUrl}/api/assets`);
  }

  sendChatMessage(query: string) {
    return this.http.post<{ response: string }>(`${this.apiUrl}/api/chat`, { query });
  }

  acknowledgeAlarm() {
    return this.http.post<any>(`${this.apiUrl}/api/alarm/acknowledge`, {});
  }

  login(credentials: { username?: string; password?: string }) {
    return this.http.post<any>(`${this.apiUrl}/api/auth/login`, credentials);
  }

  escalateAlarm() {
    return this.http.post<any>(`${this.apiUrl}/api/alarm/escalate`, {});
  }

  getFaultsHistory() {
    return this.http.get<FaultRecord[]>(`${this.apiUrl}/api/faults/history`);
  }

  getNotificationsHistory() {
    return this.http.get<NotificationRecord[]>(`${this.apiUrl}/api/notifications/history`);
  }

  getSettings() {
    return this.http.get<SettingsData>(`${this.apiUrl}/api/settings`);
  }

  saveSettings(settings: SettingsData) {
    return this.http.post<any>(`${this.apiUrl}/api/settings`, settings);
  }

  getDbAlarms() {
    return this.http.get<any[]>(`${this.apiUrl}/api/db/alarms`);
  }

  getPredictiveAssets() {
    return this.http.get<any[]>(`${this.apiUrl}/api/predictive/assets`);
  }

  getPredictivePredictions(assetId: string) {
    return this.http.get<any>(`${this.apiUrl}/api/predictive/predictions/${assetId}`);
  }

  getPredictiveTelemetry(assetId: string) {
    return this.http.get<any[]>(`${this.apiUrl}/api/predictive/telemetry/${assetId}`);
  }

  getPredictiveMaintenance(assetId: string) {
    return this.http.get<any[]>(`${this.apiUrl}/api/predictive/maintenance/${assetId}`);
  }

  getHighRiskBearings() {
    return this.http.get<any[]>(`${this.apiUrl}/api/predictive/high-risk`);
  }
}
