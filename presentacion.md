---
marp: true
theme: default
size: 16:9
paginate: false
html: true
---

<style>
section {
  font-family: Arial, sans-serif;
  background: #ffffff;
  color: #243746;
  padding: 24px 48px;
  font-size: 17px;
}

h1 {
  text-align: center;
  color: #24557d;
  font-size: 32px;
  margin: 0 0 4px;
}

.subtitle {
  text-align: center;
  color: #63788a;
  font-size: 17px;
  margin-bottom: 17px;
}

.sources, .outputs {
  display: flex;
  justify-content: center;
  gap: 20px;
}

.source {
  width: 46%;
  box-sizing: border-box;
  background: #eaf3fc;
  border-radius: 10px;
  padding: 13px;
  text-align: center;
}

.source strong {
  display: block;
  color: #24557d;
  font-size: 19px;
}

.small {
  font-size: 15px;
  margin-top: 5px;
}

.arrow {
  text-align: center;
  color: #3277aa;
  font-size: 23px;
  line-height: 1;
  margin: 7px 0;
}

.core {
  background: #24557d;
  color: white;
  text-align: center;
  border-radius: 10px;
  padding: 10px;
  font-size: 17px;
}

.core strong {
  font-size: 26px;
}

.output {
  width: 46%;
  box-sizing: border-box;
  border: 2px solid #c6dbea;
  border-radius: 10px;
  padding: 10px 16px;
}

.output h2 {
  color: #24557d;
  font-size: 19px;
  margin: 0 0 6px;
}

.output ul {
  margin: 0;
  padding-left: 20px;
  font-size: 16px;
  line-height: 1.4;
}

.footer {
  margin-top: 13px;
  padding: 9px;
  background: #eaf3fc;
  border-radius: 9px;
  text-align: center;
  color: #24557d;
  font-weight: bold;
  font-size: 16px;
}
</style>

# LUCA

<div class="subtitle">
Plataforma de gestión financiera y contable
</div>

<div class="sources">
  <div class="source">
    <strong>Servicio de Impuestos Internos</strong>
    <div class="small">API SII · Desarrollo propio</div>
  </div>
  <div class="source">
    <strong>Bancos y medios de pago</strong>
    <div class="small">Fintoc · Global66 · Mercado Pago</div>
  </div>
</div>

<div class="arrow">↓ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ↓</div>

<div class="core">
  <strong>LUCA</strong><br>
  Integración · Procesamiento · Información actualizada
</div>

<div class="arrow">↓</div>

<div class="outputs">
  <div class="output">
    <h2>Inteligencia financiera</h2>
    <ul>
      <li>Ingresos y egresos</li>
      <li>F29 y proyección</li>
      <li>Concentración de gastos</li>
      <li>Top clientes y proveedores</li>
    </ul>
  </div>
  <div class="output">
    <h2>Reportes contables</h2>
    <ul>
      <li>Balance general</li>
      <li>Estado de resultados</li>
      <li>Comparativos por período</li>
      <li>Libros diario, mayor y auxiliares</li>
    </ul>
  </div>
</div>

<div class="footer">
Datos integrados · Tiempo real · Menos trabajo manual
</div>

---

<style>
section {
  font-family: Arial, sans-serif;
  background: #fff;
  color: #243746;
  padding: 28px 50px;
}
h1 {
  font-size: 34px;
  color: #24557d;
  text-align: center;
  margin: 0 0 6px;
}
.subtitle {
  text-align: center;
  color: #63788a;
  font-size: 18px;
  margin-bottom: 19px;
}
.models {
  display: flex;
  gap: 22px;
}
.model {
  width: 50%;
  box-sizing: border-box;
  border-radius: 12px;
  padding: 15px 20px;
  background: #eaf3fc;
}
.model.b {
  background: #e8f4ee;
}
.model h2 {
  font-size: 23px;
  color: #24557d;
  text-align: center;
  margin: 0 0 4px;
}
.model.b h2 { color: #28684b; }
.desc {
  text-align: center;
  font-size: 15px;
  margin-bottom: 12px;
}
.node {
  background: white;
  border: 1px solid #b6cddd;
  border-radius: 8px;
  text-align: center;
  padding: 9px;
  font-size: 17px;
  font-weight: bold;
}
.node small {
  display: block;
  font-size: 13px;
  font-weight: normal;
  margin-top: 3px;
}
.arrow {
  text-align: center;
  color: #3277aa;
  font-size: 22px;
  line-height: 1;
  margin: 5px;
}
.b .arrow { color: #28684b; }
.model p {
  font-size: 14px;
  line-height: 1.35;
  margin: 12px 0 0;
}
.example {
  background: #f2f5f8;
  border-radius: 10px;
  padding: 13px;
  margin-top: 17px;
  text-align: center;
  font-size: 17px;
}
.example strong { color: #24557d; }
.footer {
  text-align: center;
  color: #63788a;
  font-size: 15px;
  margin-top: 13px;
}
</style>

# XAPITY
<div class="subtitle">
Un agente financiero · Dos modelos de producto
</div>

<div class="models">
  <div class="model">
    <h2>A · Xapity + Luca</h2>
    <div class="desc">Agente integrado a la plataforma</div>
    <div class="node">
      XAPITY
      <small>Consulta · Propone · Ejecuta</small>
    </div>
    <div class="arrow">↕</div>
    <div class="node">
      LUCA
      <small>Servicios financieros y contables</small>
    </div>
    <div class="arrow">↕</div>
    <div class="node">
      API SII + Bancos
      <small>Datos tributarios y bancarios</small>
    </div>
    <p>
      El cliente accede a Luca y/o Xapity.
      El agente utiliza las capacidades de la plataforma.
    </p>
  </div>

  <div class="model b">
    <h2>B · Xapity independiente</h2>
    <div class="desc">Agente financiero autónomo</div>
    <div class="node">
      XAPITY
      <small>Consulta · Propone · Ejecuta</small>
    </div>
    <div class="arrow">↕</div>
    <div class="node">
      SERVICIOS PROPIOS
      <small>Procesamiento y análisis financiero</small>
    </div>
    <div class="arrow">↕</div>
    <div class="node">
      API SII PROPIA
      <small>Nuevas integraciones según necesidad</small>
    </div>
    <p>
      El cliente contrata solo Xapity.
      Sus capacidades evolucionan según los requerimientos.
    </p>
  </div>
</div>

<div class="example">
  <strong>Una misma experiencia</strong><br>
  «Xapity, todos los lunes entrégame mi estado de
  resultados, balance general y F29 actualizado».
</div>

<div class="footer">
  Consultar · Explicar · Proponer · Ejecutar · Automatizar
</div>

---

<style>
section {
  font-family: Arial, sans-serif;
  background: #ffffff;
  color: #243746;
  padding: 25px 48px;
  font-size: 17px;
}

h1 {
  text-align: center;
  color: #24557d;
  font-size: 31px;
  margin: 0 0 5px;
}

.subtitle {
  text-align: center;
  color: #63788a;
  font-size: 17px;
  margin-bottom: 17px;
}

.sources {
  display: flex;
  gap: 20px;
  justify-content: center;
}

.source {
  width: 47%;
  box-sizing: border-box;
  border-radius: 10px;
  padding: 12px 16px;
  text-align: center;
  background: #eaf3fc;
}

.source.bank {
  background: #fff1df;
}

.source strong {
  display: block;
  color: #24557d;
  font-size: 20px;
}

.source.bank strong {
  color: #99601e;
}

.source p {
  font-size: 15px;
  margin: 5px 0;
}

.options {
  font-size: 14px;
  margin-top: 7px;
  line-height: 1.4;
}

.arrow {
  text-align: center;
  font-size: 23px;
  color: #3277aa;
  line-height: 1;
  margin: 7px 0;
}

.engine {
  background: #24557d;
  color: white;
  border-radius: 11px;
  padding: 14px;
  text-align: center;
}

.engine strong {
  font-size: 24px;
}

.engine p {
  font-size: 16px;
  margin: 5px 0 0;
}

.results {
  display: flex;
  gap: 15px;
  justify-content: center;
}

.result {
  width: 32%;
  box-sizing: border-box;
  border-radius: 9px;
  padding: 12px;
  text-align: center;
  background: #e5f4ea;
}

.result.pending {
  background: #fff3d6;
}

.result.review {
  background: #fce8e6;
}

.result strong {
  font-size: 18px;
  display: block;
  margin-bottom: 5px;
}

.result p {
  font-size: 14px;
  margin: 0;
}

.footer {
  margin-top: 17px;
  padding: 11px;
  background: #eaf3fc;
  border-radius: 9px;
  text-align: center;
  color: #24557d;
  font-size: 17px;
  font-weight: bold;
}
</style>

# XAPITY · Conciliación bancaria

<div class="subtitle">
¿Cómo sabemos si una factura está pagada o cobrada?
</div>

<div class="sources">

  <div class="source">
    <strong>DOCUMENTOS TRIBUTARIOS</strong>
    <p>API SII · Desarrollo propio</p>
    <div class="options">
      Facturas emitidas y recibidas<br>
      Clientes · Proveedores · Montos
    </div>
  </div>

  <div class="source bank">
    <strong>MOVIMIENTOS BANCARIOS</strong>
    <p>El desafío de integración</p>
    <div class="options">
      Opción 1: Fintoc / Global66 / Mercado Pago<br>
      Opción 2: Carga de cartolas bancarias
    </div>
  </div>

</div>

<div class="arrow">↓ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ↓</div>

<div class="engine">
  <strong>MOTOR DE CONCILIACIÓN PROPIO</strong>
  <p>
    Algoritmos de matching · Reglas de negocio ·
    Validación de montos y fechas
  </p>
  <p>
    Ventas · Compras · Remuneraciones · F29 · Traspasos
  </p>
</div>

<div class="arrow">↓</div>

<div class="results">

  <div class="result">
    <strong>CONCILIADO</strong>
    <p>
      Pagos y cobros identificados mediante
      movimientos bancarios
    </p>
  </div>

  <div class="result pending">
    <strong>PENDIENTE</strong>
    <p>
      Documentos sin pagos o cobros
      identificados
    </p>
  </div>

  <div class="result review">
    <strong>REVISIÓN</strong>
    <p>
      Diferencias, pagos parciales
      o coincidencias ambiguas
    </p>
  </div>

</div>

<div class="footer">
  Tecnología propia · Conciliación automatizada ·
  Información financiera más confiable
</div>

---

<style>
section {
  font-family: Arial, sans-serif;
  background: #ffffff;
  color: #243746;
  padding: 25px 48px;
  font-size: 17px;
}
h1 {
  text-align: center;
  color: #24557d;
  font-size: 32px;
  margin: 0 0 5px;
}
.subtitle {
  text-align: center;
  color: #63788a;
  font-size: 17px;
  margin-bottom: 22px;
}
.columns {
  display: flex;
  gap: 22px;
  align-items: stretch;
}
.column {
  width: 50%;
  box-sizing: border-box;
  background: #eaf3fc;
  border-radius: 12px;
  padding: 18px 20px;
}
.column.commercial {
  background: #fff1df;
}
.column h2 {
  font-size: 22px;
  color: #24557d;
  margin: 0 0 15px;
}
.column.commercial h2 {
  color: #99601e;
}
.task {
  background: #ffffff;
  border-radius: 8px;
  padding: 11px 13px;
  margin-bottom: 11px;
}
.task strong {
  display: block;
  color: #24557d;
  font-size: 17px;
  margin-bottom: 5px;
}
.commercial .task strong {
  color: #99601e;
}
.task p {
  font-size: 15px;
  line-height: 1.35;
  margin: 0;
}
.footer {
  margin-top: 19px;
  background: #eaf3fc;
  border-radius: 10px;
  padding: 13px;
  text-align: center;
}
.footer strong {
  color: #24557d;
  font-size: 18px;
}
.footer p {
  font-size: 16px;
  margin: 6px 0 0;
}
</style>

# XAPITY · Próximos pasos

<div class="subtitle">Exploración comercial y evolución conjunta del producto</div>

<div class="columns">
<div class="column commercial">
<h2>Exploración comercial</h2>
<div class="task">
<strong>01 · Modelo de negocio</strong>
<p>Evaluar Xapity + Luca y Xapity independiente. Explorar precios, márgenes y comisiones por venta.</p>
</div>
<div class="task">
<strong>02 · Clientes objetivo</strong>
<p>Identificar segmentos y oportunidades: contadores, pymes y ejecutivos financieros.</p>
</div>
<div class="task">
<strong>03 · Levantamiento de requerimientos</strong>
<p>Detectar tareas financieras repetitivas que puedan automatizarse mediante agentes.</p>
</div>
<div class="task">
<strong>04 · Experiencia del usuario</strong>
<p>Explorar canales de interacción: web, WhatsApp, correo y otros.</p>
</div>
<div class="task">
<strong>05 · Primeros contactos</strong>
<p>Identificar potenciales clientes interesados en validar casos de uso o participar en pilotos.</p>
</div>
</div>
<div class="column">
<h2>Arquitectura y producto</h2>
<div class="task">
<strong>06 · Arquitectura de Xapity</strong>
<p>Definir el agente, sus herramientas, autonomía y mecanismos de autorización.</p>
</div>
<div class="task">
<strong>07 · Demostración y piloto</strong>
<p>Preparar casos de uso reales, demostraciones y una primera versión piloto.</p>
</div>
</div>
</div>

<div class="footer">
<strong>Objetivo de nuestra próxima reunión</strong>
<p>Revisar oportunidades comerciales → Priorizar casos de uso → Definir un primer piloto</p>
</div>

---

<style>
section {
  font-family: Arial, sans-serif;
  background: #ffffff;
  color: #243746;
  padding: 24px 48px;
  font-size: 17px;
}
h1 {
  text-align: center;
  color: #24557d;
  font-size: 32px;
  margin: 0 0 5px;
}
.subtitle {
  text-align: center;
  color: #63788a;
  font-size: 17px;
  margin-bottom: 17px;
}
.problem {
  background: #fff1df;
  border-radius: 10px;
  padding: 12px 18px;
  margin-bottom: 12px;
  font-size: 16px;
}
.problem strong {
  color: #99601e;
  font-size: 19px;
}
.problem p {
  margin: 5px 0 0;
}
.flow {
  display: flex;
  gap: 12px;
  align-items: stretch;
}
.step {
  flex: 1;
  background: #eaf3fc;
  border-radius: 10px;
  padding: 13px 12px;
  text-align: center;
}
.step strong {
  display: block;
  color: #24557d;
  font-size: 18px;
  margin-bottom: 7px;
}
.step p {
  font-size: 15px;
  line-height: 1.35;
  margin: 0;
}
.arrow {
  align-self: center;
  color: #3277aa;
  font-size: 26px;
}
.results {
  display: flex;
  gap: 20px;
  margin-top: 15px;
}
.result {
  flex: 1;
  background: #e8f4ee;
  border-radius: 10px;
  padding: 13px 16px;
  text-align: center;
}
.result.admin {
  background: #eaf3fc;
}
.result strong {
  display: block;
  font-size: 18px;
  color: #28684b;
  margin-bottom: 5px;
}
.result.admin strong {
  color: #24557d;
}
.result p {
  font-size: 15px;
  margin: 0;
}
.footer {
  margin-top: 16px;
  background: #24557d;
  color: white;
  border-radius: 9px;
  padding: 12px;
  text-align: center;
  font-size: 17px;
}
</style>

# XAPITY ACCESS

<div class="subtitle">Registro digital y control de ingreso de visitantes</div>

<div class="problem">
<strong>El problema actual</strong>
<p>Registro manual en recepción: papel, lápiz, nombre, RUT, teléfono, fecha y firma. El visitante debe repetir el procedimiento cada vez que ingresa.</p>
</div>

<div class="flow">
<div class="step">
<strong>01 · Registro inicial</strong>
<p>El visitante crea su cuenta con sus datos personales, correo y contraseña.</p>
</div>
<div class="arrow">→</div>
<div class="step">
<strong>02 · Verificación</strong>
<p>Recibe un código por correo, valida su identidad digital e inicia sesión.</p>
</div>
<div class="arrow">→</div>
<div class="step">
<strong>03 · Código QR</strong>
<p>Al llegar al establecimiento, escanea el QR desde su sesión de Xapity.</p>
</div>
<div class="arrow">→</div>
<div class="step">
<strong>04 · Registro de ingreso</strong>
<p>El sistema valida la sesión y registra automáticamente la fecha y hora.</p>
</div>
</div>

<div class="results">
<div class="result">
<strong>XAPITY · VISITANTE</strong>
<p>Confirmación inmediata del ingreso registrado, sin completar nuevamente sus datos.</p>
</div>
<div class="result admin">
<strong>XAPITY · RECEPCIÓN</strong>
<p>Notificación del ingreso, identificación del visitante e historial actualizado.</p>
</div>
</div>

<div class="footer">
Una sola inscripción · Ingresos mediante QR · Registro digital automatizado
</div>

---

<style>
section {
  font-family: Arial, sans-serif;
  background: #ffffff;
  color: #243746;
  padding: 24px 48px;
  font-size: 17px;
}
h1 {
  text-align: center;
  color: #24557d;
  font-size: 31px;
  margin: 0 0 5px;
}
.subtitle {
  text-align: center;
  color: #63788a;
  font-size: 17px;
  margin-bottom: 16px;
}
.existing {
  background: #e8f4ee;
  border-radius: 10px;
  padding: 13px;
  text-align: center;
}
.existing strong {
  display: block;
  color: #28684b;
  font-size: 22px;
  margin-bottom: 4px;
}
.existing p {
  margin: 0;
  font-size: 16px;
}
.arrow {
  text-align: center;
  color: #3277aa;
  font-size: 22px;
  line-height: 1;
  margin: 7px 0;
}
.modules {
  display: flex;
  gap: 20px;
}
.module {
  flex: 1;
  background: #eaf3fc;
  border-radius: 10px;
  padding: 13px 17px;
  text-align: center;
}
.module strong {
  display: block;
  color: #24557d;
  font-size: 19px;
  margin-bottom: 6px;
}
.module p {
  margin: 0;
  font-size: 15px;
  line-height: 1.35;
}
.service {
  background: #24557d;
  color: white;
  border-radius: 10px;
  padding: 13px;
  text-align: center;
}
.service strong {
  display: block;
  font-size: 21px;
  margin-bottom: 5px;
}
.service p {
  font-size: 15px;
  margin: 0;
}
.database {
  background: #eaf3fc;
  border-radius: 10px;
  padding: 11px;
  text-align: center;
}
.database strong {
  display: block;
  color: #24557d;
  font-size: 18px;
  margin-bottom: 4px;
}
.database p {
  font-size: 15px;
  margin: 0;
}
.footer {
  margin-top: 13px;
  background: #fff1df;
  border-radius: 9px;
  padding: 10px 15px;
  text-align: center;
  font-size: 15px;
}
.footer strong {
  color: #99601e;
}
</style>

# XAPITY ACCESS · Arquitectura

<div class="subtitle">Aprovechar la tecnología existente y desarrollar el módulo de control de ingreso</div>

<div class="existing">
<strong>XAPITY · TECNOLOGÍA EXISTENTE</strong>
<p>Registro de usuarios · Verificación de correo · Login · Dashboard</p>
</div>

<div class="arrow">↓</div>

<div class="modules">
<div class="module">
<strong>Módulo Visitante</strong>
<p>Perfil personal, escaneo de código QR y confirmación del ingreso.</p>
</div>
<div class="module">
<strong>Módulo Administrador</strong>
<p>Panel de recepción, visitantes, notificaciones e historial de ingresos.</p>
</div>
</div>

<div class="arrow">↓</div>

<div class="service">
<strong>SERVICIO PROPIO DE CONTROL DE ACCESO</strong>
<p>Validación de sesión · Identificación del QR · Registro de eventos · Notificaciones</p>
</div>

<div class="arrow">↓</div>

<div class="database">
<strong>BASE DE DATOS DE INGRESOS</strong>
<p>Usuario · Establecimiento · Fecha y hora · Estado del ingreso · Historial</p>
</div>

<div class="footer">
<strong>Decisiones para el piloto:</strong> QR fijo o dinámico · Firma digitalizada · Protección de datos · Registro asistido
</div>

---

<style>
section {
  font-family: Arial, sans-serif;
  background: #ffffff;
  color: #243746;
  padding: 28px 48px;
  font-size: 17px;
}
h1 {
  text-align: center;
  color: #24557d;
  font-size: 31px;
  margin: 0 0 5px;
}
.subtitle {
  text-align: center;
  color: #63788a;
  font-size: 17px;
  margin-bottom: 18px;
}
.columns {
  display: flex;
  gap: 20px;
  align-items: stretch;
}
.column {
  width: 50%;
  box-sizing: border-box;
  background: #eaf3fc;
  border-radius: 12px;
  padding: 16px 19px;
}
.column.green {
  background: #e8f4ee;
}
.column h2 {
  color: #24557d;
  font-size: 21px;
  margin: 0 0 12px;
}
.column.green h2 {
  color: #28684b;
}
.item {
  background: #ffffff;
  border-radius: 8px;
  padding: 10px 13px;
  margin-bottom: 10px;
}
.item strong {
  display: block;
  color: #24557d;
  font-size: 17px;
  margin-bottom: 4px;
}
.item p {
  font-size: 15px;
  line-height: 1.35;
  margin: 0;
}
.green .item strong {
  color: #28684b;
}
.footer {
  margin-top: 17px;
  padding: 12px;
  background: #24557d;
  color: white;
  border-radius: 10px;
  text-align: center;
  font-size: 17px;
}
.three {
  display: flex;
  gap: 17px;
  align-items: stretch;
}
.panel {
  width: 33.33%;
  box-sizing: border-box;
  background: #eaf3fc;
  border-radius: 12px;
  padding: 15px;
}
.panel.orange {
  background: #fff1df;
}
.panel.green {
  background: #e8f4ee;
}
.panel h2 {
  font-size: 20px;
  color: #24557d;
  margin: 0 0 12px;
}
.panel.orange h2 {
  color: #99601e;
}
.panel.green h2 {
  color: #28684b;
}
.panel .item {
  padding: 9px 11px;
  margin-bottom: 9px;
}
.panel .item strong {
  font-size: 16px;
}
.panel .item p {
  font-size: 14px;
}
.panel.orange .item strong {
  color: #99601e;
}
.panel.green .item strong {
  color: #28684b;
}
</style>

# XAPITY ACCESS · Plataforma de gestión

<div class="subtitle">Usuarios · Presencia · Fidelización · Gestión operacional</div>

<div class="columns">
<div class="column">
<h2>Control de ingreso · Piloto inicial</h2>
<div class="item">
<strong>01 · Registro de usuarios</strong>
<p>Cuenta personal, correo verificado y datos del visitante. Una única inscripción.</p>
</div>
<div class="item">
<strong>02 · Validación de ingreso</strong>
<p>Escaneo QR desde una sesión activa, comprobación de ubicación y verificación presencial cuando corresponda.</p>
</div>
<div class="item">
<strong>03 · Registro automatizado</strong>
<p>Fecha, hora, establecimiento e identificación del visitante.</p>
</div>
<div class="item">
<strong>04 · Confirmación inmediata</strong>
<p>Notificación al visitante y actualización del panel de recepción.</p>
</div>
</div>
<div class="column green">
<h2>Evolución de la plataforma</h2>
<div class="item">
<strong>Fidelización</strong>
<p>Puntos, membresías, beneficios y promociones asociados a visitas verificadas.</p>
</div>
<div class="item">
<strong>Gestión operacional</strong>
<p>Horarios, reservas, capacidad del establecimiento y estadísticas de asistencia.</p>
</div>
<div class="item">
<strong>Agendamiento de turnos</strong>
<p>Planificación de turnos, asignación de horarios y gestión de disponibilidad.</p>
</div>
<div class="item">
<strong>Información y reportes</strong>
<p>Historial de visitas, frecuencia de asistencia y reportes para administradores.</p>
</div>
</div>
</div>

<div class="footer">
Xapity Access: de un registro digital a una plataforma integral de gestión
</div>

---

# XAPITY ACCESS · Próximos pasos

<div class="subtitle">Aspectos por definir y oportunidades de desarrollo</div>

<div class="three">
<div class="panel">
<h2>01 · Validación de ingreso</h2>
<div class="item">
<strong>QR dinámico</strong>
<p>Código de corta duración, validado por el servidor.</p>
</div>
<div class="item">
<strong>Geolocalización</strong>
<p>Comprobar que el dispositivo esté dentro del perímetro del establecimiento.</p>
</div>
<div class="item">
<strong>Identificación presencial</strong>
<p>Verificación del carnet de identidad cuando sea necesaria.</p>
</div>
<div class="item">
<strong>Seguridad</strong>
<p>Definir cómo evitar registros remotos, suplantaciones y uso compartido de credenciales.</p>
</div>
</div>
<div class="panel orange">
<h2>02 · Firma y registro</h2>
<div class="item">
<strong>Propósito de la firma</strong>
<p>Determinar si acredita aceptación de condiciones, normas de seguridad u otras responsabilidades.</p>
</div>
<div class="item">
<strong>Firma electrónica</strong>
<p>Evaluar si es necesaria y qué mecanismo corresponde utilizar.</p>
</div>
<div class="item">
<strong>Dashboard del usuario</strong>
<p>Mostrar condiciones aceptadas, fecha de aceptación e historial de ingresos.</p>
</div>
<div class="item">
<strong>Protección de datos</strong>
<p>Definir permisos, finalidad del registro y conservación de información personal.</p>
</div>
</div>
<div class="panel green">
<h2>03 · Turnos y agendamiento</h2>
<div class="item">
<strong>Planificación de turnos</strong>
<p>Asignar horarios a trabajadores y responsables del establecimiento.</p>
</div>
<div class="item">
<strong>Disponibilidad</strong>
<p>Gestionar cobertura, capacidad y cambios de turno.</p>
</div>
<div class="item">
<strong>Reservas</strong>
<p>Agendar citas, espacios y servicios desde la plataforma.</p>
</div>
<div class="item">
<strong>Notificaciones</strong>
<p>Recordatorios, confirmaciones y avisos de cambios de horario.</p>
</div>
</div>
</div>

<div class="footer">
Primer piloto: validar ingresos y firma · Evolución: fidelización y agendamiento
</div>

