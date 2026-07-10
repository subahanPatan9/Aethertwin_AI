import { Component, signal, computed, inject, OnInit, effect, untracked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TelemetryService, Telemetry } from './services/telemetry.service';

@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App implements OnInit {
  // Service injection
  public telemetryService = inject(TelemetryService);

  // Component UI State
  activeTab = signal<string>('dashboard');

  // Authentication UI States (Point 3)
  isAuthenticated = signal<boolean>(false);
  userRole = signal<'OPERATOR' | 'ENGINEER' | null>(null);
  usernameInput = 'GOH0972.HYD016@hackathonindia.net';
  passwordInput = 'HYD@40*065';
  loginError = '';
  loginName = signal<string>('');

  login() {
    this.loginError = '';
    this.telemetryService.login({ username: this.usernameInput, password: this.passwordInput }).subscribe({
      next: (res) => {
        this.isAuthenticated.set(true);
        this.userRole.set(res.role);
        this.loginName.set(res.name);
        this.addToast('success', 'Access Granted', `Welcome back, ${res.name}. Dynamic SCADA workspace unlocked.`);
        
        // Initialise data loaders upon authentication
        this.loadDtdlData();
        this.loadAssetsData();
        this.loadFaultsHistory();
        this.loadNotificationsHistory();
        this.loadSettings();
        this.loadDbAlarms();
        this.loadPredictiveAssets();
      },
      error: (err) => {
        console.error('Login error:', err);
        this.loginError = err.error?.detail || 'Unauthorized connection. Please check credentials.';
      }
    });
  }

  logout() {
    this.isAuthenticated.set(false);
    this.userRole.set(null);
    this.loginName.set('');
    this.addToast('info', 'Logged Out', 'Your session has been securely closed.');
  }
  
  // Local forms/sliders bindings
  inputRpm = 1500;
  inputV101 = 100;
  inputV102 = 100;
  inputDrain = 50;

  // Audio variables
  private alarmInterval: any = null;
  private audioCtx: AudioContext | null = null;
  public isMuted = signal<boolean>(false);

  // Toast / Alerts stack
  public toasts = signal<Array<{ id: number; type: string; title: string; message: string }>>([]);

  // Alarm Modal States
  public isAlarmModalOpen = signal<boolean>(false);
  public activeAlarmDetails = signal<{ title: string; message: string; faultType: string } | null>(null);
  private lastFaultState = 'NORMAL';

  // Alarm Escalation States (Point 9)
  public isEscalated = signal<boolean>(false);
  public escalationCountdown = signal<number>(15);
  public escalationTimeElapsed = signal<number>(0);
  public escalatedLevel = signal<number>(0);
  public isTimeAcceleration = signal<boolean>(false);
  private escalationInterval: any = null;

  // CMDB & Assets inventory
  public assets = signal<any[]>([]);

  // Issue Log & History (Point 2)
  public faultsHistory = signal<any[]>([]);
  public notificationsHistory = signal<any[]>([]);
  
  public totalAlerts = computed(() => this.faultsHistory().length);
  public resolvedAlerts = computed(() => this.faultsHistory().filter(f => f.status === 'Resolved').length);
  public pendingAlerts = computed(() => this.faultsHistory().filter(f => f.status === 'Critical' || f.status === 'Pending').length);
  public inProgressAlerts = computed(() => this.faultsHistory().filter(f => f.status === 'In Progress').length);
  // DB Alarms & Predictive Maintenance (Point 7 & 8)
  public dbAlarms = signal<any[]>([]);
  public issuesSubTab = signal<'incidents' | 'dbalarms'>('incidents');

  public predictiveAssets = signal<any[]>([]);
  public selectedPredictiveAssetId = signal<string>('Pump-101');
  public predictiveData = signal<any>(null);
  public predictiveTelemetry = signal<any[]>([]);
  public predictiveMaintenance = signal<any[]>([]);
  public selectedDigitalTwinAsset = signal<any | null>(null);

  // Settings Forms & Polling Limits (Point 4)
  public settingsForm = {
    normal_flow_setpoint: 15.0,
    max_pressure_threshold: 45.0,
    target_water_level: 80.0,
    twilio_sid: '',
    twilio_token: '',
    twilio_from: '',
    operator_phone: '',
    polling_rate: 1000
  };

  // Mobile navigation drawer toggle (Point 6)
  public isMobileMenuOpen = signal<boolean>(false);

  // Forensic Incident detail selection (Point 2)
  public selectedIncident = signal<any | null>(null);

  // Chat Assistant states
  public chatQuery = '';
  public chatMessages = signal<Array<{ sender: 'user' | 'bot'; text: string }>>([
    { sender: 'bot', text: 'Hello! I am your generative AetherTwin AI Assistant. How can I help you inspect system health or CMDB records today?' }
  ]);
  public isChatLoading = signal<boolean>(false);

  constructor() {
    // Watch for fault changes using Angular Signal effect
    effect(() => {
      const fault = this.telemetryService.activeFault();
      
      // Only execute state change when activeFault actually transitions to a new state
      if (fault !== this.lastFaultState) {
        this.lastFaultState = fault;
        
        if (fault !== 'NORMAL') {
          this.startAlarm();
          this.startEscalationCountdown();
          
          // Trigger-time warning notification toasts for demo scenario
          this.addToast('warning', 'Predictive Alert Triggered', `AI agent predicted fault: ${fault.replace('_', ' ')}. SMS & email alerts queueing.`);
          this.addToast('success', 'SMS / Email Dispatched', 'Real-time warning notifications sent successfully to remote supervisor.');
          
          let title = `CRITICAL SYSTEM ALARM: ${fault.replace('_', ' ')}`;
          let msg = '';
          
          if (fault === 'PUMP_CAVITATION') {
            msg = 'Critical vibration spike detected on Booster Pump P-101. The inlet suction path is choked, causing vapor bubble collapse inside the impeller head. Immediate isolation required to prevent mechanical breakdown.';
          } else if (fault === 'PIPE_LEAK') {
            msg = 'Significant volumetric flow delta identified between discharge sensor FIT-101 and sand filter sensor FIT-102. Pipeline pressure has dropped, indicating high risk of a pipeline fracture.';
          } else if (fault === 'VALVE_CLOG') {
            msg = 'High-High deadhead pressure limit breached at sensor PIT-101. Downstream flow is fully blocked at sand filter F-101, causing electrical current spikes on the booster motor.';
          } else {
            msg = `Process telemetry out of safety bounds. Active system anomaly flag: ${fault}.`;
          }
          
          // Open Modal Popup with specific details
          this.activeAlarmDetails.set({ title, message: msg, faultType: fault });
          this.isAlarmModalOpen.set(true);
          
          // Add a single toast alert
          this.addToast('danger', title, msg);
        } else {
          // Normal state transition
          this.stopAlarm();
          this.stopEscalationCountdown();
          this.isAlarmModalOpen.set(false);
          this.activeAlarmDetails.set(null);
          this.addToast('success', 'System Restored', 'All process lines and sensors are within normal technical specifications.');
        }
      }
    });
  }

  // Toast management
  addToast(type: string, title: string, message: string) {
    const id = Date.now();
    this.toasts.update(t => [...t, { id, type, title, message }]);
    
    // Auto remove after 6 seconds
    setTimeout(() => {
      this.removeToast(id);
    }, 6000);
  }

  removeToast(id: number) {
    this.toasts.update(t => t.filter(x => x.id !== id));
  }

  // Assets / CMDB loader
  loadAssetsData() {
    this.telemetryService.getAssets().subscribe({
      next: (res) => this.assets.set(res),
      error: (err) => console.error('Error loading CMDB assets:', err)
    });
  }

  // Chat Query handler
  sendChatMessage() {
    const query = this.chatQuery.trim();
    if (!query) return;

    this.chatMessages.update(msgs => [...msgs, { sender: 'user', text: query }]);
    this.chatQuery = '';
    this.isChatLoading.set(true);

    this.telemetryService.sendChatMessage(query).subscribe({
      next: (res) => {
        this.chatMessages.update(msgs => [...msgs, { sender: 'bot', text: res.response }]);
        this.isChatLoading.set(false);
        this.scrollToChatBottom();
      },
      error: (err) => {
        console.error('Chat error:', err);
        this.chatMessages.update(msgs => [...msgs, { sender: 'bot', text: 'Sorry, I encountered an issue processing your query. Please ensure backend is online.' }]);
        this.isChatLoading.set(false);
        this.scrollToChatBottom();
      }
    });
  }

  applyChatQuery(queryText: string) {
    this.chatQuery = queryText;
    this.sendChatMessage();
  }

  formatChatMessage(text: string): string {
    if (!text) return '';
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
      
    // 1. Headers (### Header)
    html = html.replace(/^### (.*?)$/gm, '<h3 class="chat-header-h3" style="color: var(--primary); margin-top: 0.8rem; margin-bottom: 0.4rem; font-weight: 750;">$1</h3>');
    html = html.replace(/^## (.*?)$/gm, '<h4 class="chat-header-h4" style="color: var(--primary); margin-top: 0.6rem; margin-bottom: 0.3rem;">$1</h4>');
    
    // 2. Bold (**text**)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong style="color: #38bdf8;">$1</strong>');
    
    // 3. Code blocks (```code```)
    html = html.replace(/```([\s\S]*?)```/g, '<pre class="chat-code-block" style="background: rgba(8,10,18,0.7); border: 1px solid rgba(255,255,255,0.06); padding: 0.5rem; border-radius: 4px; overflow-x: auto; margin: 0.5rem 0;"><code style="font-family: monospace; font-size: 0.75rem;">$1</code></pre>');
    
    // 4. Inline code (`code`)
    html = html.replace(/`(.*?)`/g, '<code class="chat-inline-code" style="background: rgba(255,255,255,0.08); padding: 1px 4px; border-radius: 3px; font-family: monospace; font-size: 0.8rem; color: #f43f5e;">$1</code>');
    
    // 5. Bullet Lists (- item or * item)
    html = html.replace(/^\s*[-*]\s+(.*?)$/gm, '<li class="chat-list-item" style="margin-left: 1rem; list-style-type: disc; font-size: 0.85rem; margin-bottom: 0.2rem;">$1</li>');
    
    // 6. Line breaks
    html = html.replace(/\n/g, '<br/>');
    
    return html;
  }

  scrollToChatBottom() {
    setTimeout(() => {
      const chatScroll = document.querySelector('.chat-messages-scroll');
      if (chatScroll) {
        chatScroll.scrollTop = chatScroll.scrollHeight;
      }
    }, 100);
  }

  // Escalation Countdown timer
  startEscalationCountdown() {
    this.stopEscalationCountdown();
    this.isEscalated.set(false);
    this.escalationTimeElapsed.set(0);
    this.escalatedLevel.set(0);
    this.escalationCountdown.set(30); // Show countdown to voice call initially
    
    this.escalationInterval = setInterval(() => {
      // Tick based on acceleration state
      const delta = this.isTimeAcceleration() ? 20 : 1;
      const elapsed = Math.min(600, this.escalationTimeElapsed() + delta);
      this.escalationTimeElapsed.set(elapsed);

      // Map countdown remaining for the active step
      if (elapsed < 30) {
        this.escalationCountdown.set(30 - elapsed);
      } else if (elapsed < 120) {
        this.escalationCountdown.set(120 - elapsed);
      } else if (elapsed < 300) {
        this.escalationCountdown.set(300 - elapsed);
      } else if (elapsed < 600) {
        this.escalationCountdown.set(600 - elapsed);
      } else {
        this.escalationCountdown.set(0);
      }

      // Check milestones
      // Milestone 1: Voice bot call at 30s
      if (elapsed >= 30 && this.escalatedLevel() < 1) {
        this.escalatedLevel.set(1);
        this.addToast('info', '📞 Voice Bot Call Active', 'Placing automated speech warning call to Control Room operator.');
      }
      
      // Milestone 2: Shift Engineer SMS/Email at 2m (120s)
      if (elapsed >= 120 && this.escalatedLevel() < 2) {
        this.escalatedLevel.set(2);
        this.addToast('warning', '✉️ SLA Escalate Level 1', 'Shift Engineer notified via emergency SMS and email.');
        this.telemetryService.escalateAlarm().subscribe({
          next: () => this.loadNotificationsHistory(),
          error: () => this.loadNotificationsHistory()
        });
      }

      // Milestone 3: Maintenance Manager at 5m (300s)
      if (elapsed >= 300 && this.escalatedLevel() < 3) {
        this.escalatedLevel.set(3);
        this.addToast('danger', '🚨 SLA Escalate Level 2', 'Shift Engineer failed to respond. Maintenance Manager notified.');
      }

      // Milestone 4: Plant Head at 10m (600s)
      if (elapsed >= 600 && this.escalatedLevel() < 4) {
        this.escalatedLevel.set(4);
        this.isEscalated.set(true);
        this.addToast('danger', '💥 CRITICAL SLA BREACH', 'Maintenance Manager failed to respond. Plant Head notified. Emergency shutdown authorized.');
        this.stopEscalationCountdown();
      }
    }, 1000);
  }

  stopEscalationCountdown() {
    if (this.escalationInterval) {
      clearInterval(this.escalationInterval);
      this.escalationInterval = null;
    }
    this.isEscalated.set(false);
    this.escalationCountdown.set(15);
    this.escalationTimeElapsed.set(0);
    this.escalatedLevel.set(0);
  }

  acknowledgeAlarm() {
    this.telemetryService.acknowledgeAlarm().subscribe({
      next: () => {
        this.stopEscalationCountdown();
        this.stopAlarm();
        this.addToast('success', 'Alarm Acknowledged', 'System alarm acknowledged. Escalation sequence suspended.');
      },
      error: (err) => console.error('Error acknowledging alarm:', err)
    });
  }

  // Modal actions
  silenceAndCloseModal() {
    this.stopAlarm();
    this.isAlarmModalOpen.set(false);
  }

  openDiagnosticsTab() {
    this.stopAlarm();
    this.isAlarmModalOpen.set(false);
    this.activeTab.set('copilot');
  }

  executeSafetyInterlockFromModal() {
    this.stopAlarm();
    this.isAlarmModalOpen.set(false);
    this.applyMitigationAndSwitchBack();
  }

  toggleMute() {
    this.isMuted.update(m => !m);
    if (this.isMuted()) {
      this.stopAlarm();
    } else if (this.telemetryService.activeFault() !== 'NORMAL') {
      this.startAlarm();
    }
  }

  startAlarm() {
    if (this.isMuted()) return;
    if (this.alarmInterval) return; // Already running

    this.alarmInterval = setInterval(() => {
      this.playBeep();
    }, 1000);
  }

  stopAlarm() {
    if (this.alarmInterval) {
      clearInterval(this.alarmInterval);
      this.alarmInterval = null;
    }
  }

  private playBeep() {
    try {
      if (this.isMuted()) return;
      if (!this.audioCtx) {
        this.audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      
      const ctx = this.audioCtx;
      if (ctx.state === 'suspended') {
        ctx.resume();
      }

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(650, ctx.currentTime);
      
      gain.gain.setValueAtTime(0.08, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start();
      osc.stop(ctx.currentTime + 0.6);
    } catch (e) {
      console.warn('Audio alarm blocked or unsupported:', e);
    }
  }

  // Azure DevOps Work Order form
  woPriority = 'HIGH';
  woComponent = 'P-101';
  woDescription = 'AI Anomaly Copilot flagged cavitation/thermal stress. Dispatched for seals inspection.';
  createdWorkOrder = signal<any>(null);
  creatingWorkOrder = signal<boolean>(false);

  // DTDL models list for display
  dtdlModels = signal<any[]>([]);
  loadingDtdl = signal<boolean>(false);

  // Selected fault to trigger in simulation dashboard
  selectedFaultToTrigger = 'NORMAL';

  // Presentation Guide steps
  presentationSteps = [
    {
      title: "1. Baseline Healthy Run",
      description: "Start the plant in healthy mode. Show the fluid flowing through animated pipes, tank levels shifting, and sensors sitting at normal parameters. Emphasize that the system is stable.",
      actionLabel: "Set System to Healthy",
      action: () => this.setNormalState()
    },
    {
      title: "2. Starve the Suction (Pump Cavitation)",
      description: "Simulate a severe failure mode. We shut valve V-101 (or trigger cavitation). Watch the pump vibration spike (>8 mm/s), motor temp skyrocket (>70°C), and water flow flatline. The AI alarm will immediately glow red.",
      actionLabel: "Trigger Cavitation Fault",
      action: () => this.triggerSelectedFault('PUMP_CAVITATION')
    },
    {
      title: "3. Consult the Generative Copilot",
      description: "Click the 'AI Copilot' tab. Show the judges the automatic Root Cause Analysis (RCA) explaining why the pump is cavitating, along with the dynamically generated IEC 61131-3 Structured Text PLC code to solve it.",
      actionLabel: "View AI Resolution Plan",
      action: () => this.activeTab.set('copilot')
    },
    {
      title: "4. Apply AI Safe Interlock",
      description: "Click 'Apply AI Mitigation'. The backend applies safety code, trips the pump to 0 RPM, resets the system to safety, and highlights the recovery flow. This demonstrates autonomous edge safety.",
      actionLabel: "Execute AI Mitigation",
      action: () => this.applyMitigationAndSwitchBack()
    },
    {
      title: "5. Generate Azure Twin Graph",
      description: "Go to the 'Azure Digital Twin' tab. Display the automatically generated DTDL schema and show how the physical topology maps directly to Microsoft's cloud twin model to update cloud twins in real-time.",
      actionLabel: "Show Azure DTDL Sync",
      action: () => this.activeTab.set('dtdl')
    }
  ];
  currentPresentationStep = signal<number>(0);

  ngOnInit() {
    this.loadDtdlData();
    this.loadAssetsData();
  }

  // Set local control inputs from live telemetry state (if they are adjusted)
  syncControls() {
    const live = this.telemetryService.liveData();
    if (live && live.telemetry) {
      this.inputRpm = live.telemetry.pump_rpm;
      this.inputV101 = live.telemetry.valve_v101_open;
      this.inputV102 = live.telemetry.valve_v102_open;
      this.inputDrain = live.telemetry.drain_valve_open;
      this.addToast('success', 'Control Loops Synced', 'Process control sliders synchronized to live telemetry.');
    } else {
      this.addToast('warning', 'Sync Deferred', 'Unable to sync. Waiting for active telemetry connection.');
    }
  }

  // Trigger slider updates to API
  sendControlUpdate() {
    this.telemetryService.updateControls({
      pump_rpm: this.inputRpm,
      valve_v101_open: this.inputV101,
      valve_v102_open: this.inputV102,
      drain_valve_open: this.inputDrain
    });
  }

  triggerSelectedFault(fault: string) {
    this.selectedFaultToTrigger = fault;
    this.telemetryService.triggerFault(fault);
    
    // Automatically fill work order details matching the fault
    if (fault === 'PUMP_CAVITATION') {
      this.woComponent = 'P-101';
      this.woDescription = 'AI Anomaly detector flagged Critical Cavitation on Booster Pump P-101. Vibration > 8mm/s, Temperature > 70°C. Urgent inspection of impeller seals required.';
    } else if (fault === 'PIPE_LEAK') {
      this.woComponent = 'PIPE-SECTION-2';
      this.woDescription = 'Mass-flow differential leak detected between discharge FIT-101 and filter FIT-102. Pipeline pressure drop. Immediate pipe gasket inspection required.';
    } else if (fault === 'VALVE_CLOG') {
      this.woComponent = 'F-101 / V-102';
      this.woDescription = 'High deadhead pressure (>55 PSI) detected at filter inlet PIT-101 with low flow output. Automated backwash initiated. Manual inspection required.';
    }
    
    // Reset work order state for new fault
    this.createdWorkOrder.set(null);
  }

  setNormalState() {
    this.triggerSelectedFault('NORMAL');
    // Set typical healthy run parameters
    this.inputRpm = 1800;
    this.inputV101 = 100;
    this.inputV102 = 100;
    this.inputDrain = 40;
    this.sendControlUpdate();
  }

  applyMitigationAndSwitchBack() {
    this.telemetryService.applyMitigation();
    // Sync local sliders to 0 pump RPM
    this.inputRpm = 0;
    if (this.telemetryService.activeFault() === 'PIPE_LEAK') {
      this.inputV101 = 0;
      this.inputV102 = 0;
    }
    setTimeout(() => {
      this.syncControls();
    }, 1200);
  }

  loadDtdlData() {
    this.loadingDtdl.set(true);
    this.telemetryService.getDtdl().subscribe({
      next: (res) => {
        this.dtdlModels.set(res);
        this.loadingDtdl.set(false);
      },
      error: () => { this.loadingDtdl.set(false); }
    });
  }

  dispatchWorkOrder() {
    this.creatingWorkOrder.set(true);
    const fault = this.telemetryService.activeFault();
    this.telemetryService.createWorkOrder({
      component_id: this.woComponent,
      fault_type: fault,
      priority: this.woPriority,
      description: this.woDescription
    }).subscribe({
      next: (res) => {
        this.createdWorkOrder.set(res);
        this.creatingWorkOrder.set(false);
      },
      error: () => this.creatingWorkOrder.set(false)
    });
  }

  // Presentation step helper
  nextStep() {
    if (this.currentPresentationStep() < this.presentationSteps.length - 1) {
      this.currentPresentationStep.update(n => n + 1);
    }
  }

  prevStep() {
    if (this.currentPresentationStep() > 0) {
      this.currentPresentationStep.update(n => n - 1);
    }
  }

  runStepAction(stepIdx: number) {
    this.presentationSteps[stepIdx].action();
  }

  // --- SVG Custom Chart Computations ---
  // Calculates SVG points for rolling telemetry plots
  getChartPath(key: keyof Telemetry, minVal: number, maxVal: number, color: string): string {
    const history = this.telemetryService.telemetryHistory();
    if (history.length < 2) return '';

    const width = 500;
    const height = 150;
    const padding = 10;
    
    const points = history.map((t, idx) => {
      const x = padding + (idx / (history.length - 1)) * (width - 2 * padding);
      const val = t[key] as number;
      // Normalise val between minVal and maxVal
      const normVal = (val - minVal) / (maxVal - minVal);
      // Flip Y axis since SVG 0 is top
      const y = height - padding - normVal * (height - 2 * padding);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    return `M ${points.join(' L ')}`;
  }

  isCalibrationOverdue(dueDateStr: string): boolean {
    if (!dueDateStr) return false;
    const due = new Date(dueDateStr);
    const today = new Date();
    return due < today;
  }

  isWarrantyExpired(expiryDateStr: string): boolean {
    if (!expiryDateStr) return false;
    const expiry = new Date(expiryDateStr);
    const today = new Date();
    return expiry < today;
  }

  getProbabilityColor(val: number): string {
    if (val < 35) return '#10b981'; // Green
    if (val < 70) return '#f59e0b'; // Yellow/Orange
    return '#ef4444'; // Red
  }

  loadDbAlarms() {
    this.telemetryService.getDbAlarms().subscribe({
      next: (res) => this.dbAlarms.set(res),
      error: (err) => console.error('Error loading DB alarms:', err)
    });
  }

  loadPredictiveAssets() {
    this.telemetryService.getPredictiveAssets().subscribe({
      next: (assets) => {
        this.predictiveAssets.set(assets);
        if (assets.length > 0 && !this.selectedPredictiveAssetId()) {
          this.selectedPredictiveAssetId.set(assets[0].asset_id);
        }
        this.loadPredictiveDetails(this.selectedPredictiveAssetId());
      },
      error: (err) => console.error('Error loading predictive assets:', err)
    });
  }

  loadPredictiveDetails(assetId: string) {
    if (!assetId) return;
    this.telemetryService.getPredictivePredictions(assetId).subscribe({
      next: (data) => {
        this.predictiveData.set(data);
        const p30 = data?.failure_probabilities?.within_30_days;
        if (p30 && p30 >= 70) {
          this.addToast('danger', '🚨 Critical Bearing Degraded', `Vibration threshold limit breached on ${assetId}. Failure probability within 30 days is ${p30}%.`);
        }
      },
      error: (err) => console.error('Error loading predictions:', err)
    });
    this.telemetryService.getPredictiveTelemetry(assetId).subscribe({
      next: (data) => this.predictiveTelemetry.set(data),
      error: (err) => console.error('Error loading predictive telemetry:', err)
    });
    this.telemetryService.getPredictiveMaintenance(assetId).subscribe({
      next: (data) => this.predictiveMaintenance.set(data),
      error: (err) => console.error('Error loading predictive maintenance logs:', err)
    });
  }

  selectPredictiveAsset(assetId: string) {
    this.selectedPredictiveAssetId.set(assetId);
    this.loadPredictiveDetails(assetId);
  }

  loadFaultsHistory() {
    this.telemetryService.getFaultsHistory().subscribe({
      next: (res) => this.faultsHistory.set(res),
      error: (err) => console.error('Error loading faults log:', err)
    });
  }

  loadNotificationsHistory() {
    this.telemetryService.getNotificationsHistory().subscribe({
      next: (res) => this.notificationsHistory.set(res),
      error: (err) => console.error('Error loading alerts history:', err)
    });
  }

  loadSettings() {
    this.telemetryService.getSettings().subscribe({
      next: (res) => {
        if (res) {
          this.settingsForm = {
            normal_flow_setpoint: res.normal_flow_setpoint || 15.0,
            max_pressure_threshold: res.max_pressure_threshold || 45.0,
            target_water_level: res.target_water_level || 80.0,
            twilio_sid: res.twilio_sid || '',
            twilio_token: res.twilio_token || '',
            twilio_from: res.twilio_from || '',
            operator_phone: res.operator_phone || '',
            polling_rate: res.polling_rate || 1000
          };
        }
      },
      error: (err) => console.error('Error loading settings:', err)
    });
  }

  saveSettings() {
    this.telemetryService.saveSettings(this.settingsForm).subscribe({
      next: () => {
        this.addToast('success', 'Parameters Synced', 'System thresholds and Twilio credentials updated successfully.');
      },
      error: (err) => {
        console.error('Error saving settings:', err);
        this.addToast('danger', 'Sync Failed', 'Failed to update system settings in database.');
      }
    });
  }

  toggleMobileMenu() {
    this.isMobileMenuOpen.update(o => !o);
  }

  switchTab(tab: string) {
    this.activeTab.set(tab);
    this.isMobileMenuOpen.set(false);
    
    if (tab === 'issues') {
      this.loadFaultsHistory();
      this.loadDbAlarms();
    } else if (tab === 'settings') {
      this.loadSettings();
      this.loadNotificationsHistory();
    } else if (tab === 'predictive') {
      this.loadPredictiveAssets();
    }
  }

  openIncidentDetail(issue: any) {
    const type = issue.type;
    const timestamp = issue.timestamp;
    const status = issue.status;
    const desc = issue.description;

    // Generate a unique ticket reference ID
    const incId = `INC-${new Date(timestamp).getTime().toString().substring(5, 11)}`;

    let impact = 'MODERATE';
    let impactText = 'Standard telemetry fluctuation. No production flow interruption.';
    let criticalAlarms: string[] = [];
    let minorAlarms: string[] = ['Minor telemetry deviation detected'];
    let estDowntime = '0 minutes';
    let actDowntime = '0 minutes';
    let maintActivities: string[] = ['Baseline calibration check'];
    let predictedFailures = 'No failures predicted. Equipment health index stable at 100%.';
    let recommendedInspections: string[] = ['Verify telemetry polling sync rate'];
    let resDuration = '0 seconds';
    
    // Telemetry Snapshot at trigger-time
    let fit101 = 12.0;
    let fit102 = 12.0;
    let pit101 = 22.0;
    let temp = 45.0;
    let vib = 0.9;
    let confidence = 98.4;

    const timeline = [
      { time: new Date(new Date(timestamp).getTime() - 1000).toISOString(), event: 'Telemetry polling baseline normal.', status: 'Normal' },
      { time: timestamp, event: `AI Anomaly Agent registered fault class: ${type}`, status: 'Anomaly Detected' }
    ];

    if (type === 'PUMP_CAVITATION') {
      impact = 'CRITICAL';
      impactText = 'Complete loss of pipeline discharge flow. Starvation of downstream filtration bed F-101. Thermal load buildup on motor windings.';
      criticalAlarms = ['VIB-101 (Motor Vibration) > 8.0 mm/s', 'TEMP-101 (Motor Temperature) > 70.0°C'];
      minorAlarms = ['FIT-101 Flow Starvation (< 2.0 L/m)', 'Pressure spike PIT-101'];
      estDowntime = '45 minutes (Manual crew dispatch)';
      actDowntime = '18 seconds (Autonomous edge safety trip)';
      maintActivities = ['Debris cleaning from V-101 suction valve seat', 'Impeller casing cavitation check', 'Motor bearing lubrication'];
      predictedFailures = 'Impeller structural fatigue and seals leakage predicted within 2.4 hours under cavitation load.';
      recommendedInspections = [
        'Inspect suction valve V-101 gate alignment',
        'Verify bearing clearance tolerances',
        'Check motor winding insulation resistance'
      ];
      resDuration = '18 seconds';
      fit101 = 1.2;
      fit102 = 1.0;
      pit101 = 38.5;
      temp = 73.5;
      vib = 8.4;
      confidence = 99.8;

      timeline.push(
        { time: new Date(new Date(timestamp).getTime() + 1000).toISOString(), event: 'Predictive toast warnings generated in dashboard UI.', status: 'Pending' },
        { time: new Date(new Date(timestamp).getTime() + 2000).toISOString(), event: 'Azure DevOps maintenance ticket WO-48201 dispatched.', status: 'In Progress' }
      );
      if (status === 'Resolved' || status === 'Normal') {
        timeline.push(
          { time: new Date(new Date(timestamp).getTime() + 15000).toISOString(), event: 'SLA countdown breached. Twilio SMS alert sent to Operator mobile device.', status: 'Escalated' },
          { time: new Date(new Date(timestamp).getTime() + 18000).toISOString(), event: 'AI Safety override code executed. Pump RPM set to 0. System isolated.', status: 'Mitigation Applied' },
          { time: new Date(new Date(timestamp).getTime() + 19000).toISOString(), event: 'Telemetry parameters stabilized. Issue status marked as Resolved.', status: 'Resolved' }
        );
      }
    } else if (type === 'PIPE_LEAK') {
      impact = 'HIGH';
      impactText = 'Volumetric flow mismatch. Liquid loss in discharge manifold. Potential refinery floor contamination hazard.';
      criticalAlarms = ['FIT-101 (Inlet Flow) vs FIT-102 (Outlet Flow) mismatch delta > 8 L/min', 'Pressure drop PIT-101 (< 15 PSI)'];
      minorAlarms = ['FIT-102 flow decrease'];
      estDowntime = '60 minutes (Manifold weld repair)';
      actDowntime = '12 seconds (Line isolation)';
      maintActivities = ['Discharge pipe pressure testing', 'Gasket seals replacement', 'Refinery floor cleanup'];
      predictedFailures = 'Complete pipeline rupture and pressure loss predicted within 1.5 hours of continuous flow.';
      recommendedInspections = [
        'Check pipe wall thickness via ultrasonic testing',
        'Verify manifold union flange gaskets',
        'Inspect valve V-102 seal integrity'
      ];
      resDuration = '12 seconds';
      fit101 = 24.5;
      fit102 = 12.1;
      pit101 = 12.8;
      temp = 48.2;
      vib = 1.4;
      confidence = 97.5;

      timeline.push(
        { time: new Date(new Date(timestamp).getTime() + 1000).toISOString(), event: 'Volumetric flow mismatch alert flagged by AI model.', status: 'Pending' },
        { time: new Date(new Date(timestamp).getTime() + 2000).toISOString(), event: 'DevOps maintenance ticket WO-48305 created.', status: 'In Progress' }
      );
      if (status === 'Resolved' || status === 'Normal') {
        timeline.push(
          { time: new Date(new Date(timestamp).getTime() + 12000).toISOString(), event: 'Automated line isolation safety interlock executed. Flow terminated.', status: 'Resolved' }
        );
      }
    } else if (type === 'VALVE_CLOG') {
      impact = 'HIGH';
      impactText = 'Deadhead pressure build-up. Impeller blockage and high motor torque load. Potential pipe weld fracture hazard.';
      criticalAlarms = ['PIT-101 (Discharge Pressure) > 42.0 PSI', 'Motor Current draw > 12.0 Amps'];
      minorAlarms = ['FIT-102 (Outlet Flow) drop (< 1 L/min)'];
      estDowntime = '90 minutes (Sand bed backwash & filter flush)';
      actDowntime = '15 seconds (Safety override)';
      maintActivities = ['Sand filter bed F-101 backwash cycle', 'Inlet strainer cleaning', 'Pressure gauge recalibration'];
      predictedFailures = 'Pipe burst or coupling shaft shear predicted within 45 minutes of deadhead pressure load.';
      recommendedInspections = [
        'Run sand bed backwash cycle on F-101',
        'Verify strainers for particulate blockages',
        'Check motor torque and coupling alignment'
      ];
      resDuration = '15 seconds';
      fit101 = 12.4;
      fit102 = 0.2;
      pit101 = 44.5;
      temp = 54.8;
      vib = 2.8;
      confidence = 99.1;

      timeline.push(
        { time: new Date(new Date(timestamp).getTime() + 1000).toISOString(), event: 'High-High deadhead pressure alarm triggered at PIT-101.', status: 'Pending' },
        { time: new Date(new Date(timestamp).getTime() + 2000).toISOString(), event: 'DevOps maintenance ticket WO-48402 created.', status: 'In Progress' }
      );
      if (status === 'Resolved' || status === 'Normal') {
        timeline.push(
          { time: new Date(new Date(timestamp).getTime() + 15000).toISOString(), event: 'SLA countdown completed. Safety bypass interlock triggered. Flow diverted.', status: 'Resolved' }
        );
      }
    }

    this.selectedIncident.set({
      id: incId,
      type,
      timestamp,
      status,
      description: desc,
      impact,
      impactText,
      criticalAlarms,
      minorAlarms,
      estDowntime,
      actDowntime,
      maintActivities,
      predictedFailures,
      recommendedInspections,
      resDuration,
      telemetry: { fit101, fit102, pit101, temp, vib, confidence },
      timeline
    });
  }

  closeIncidentDetail() {
    this.selectedIncident.set(null);
  }
}
