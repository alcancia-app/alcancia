// Pruebas de la interfaz (ui/) en un navegador real con los datos ficticios de ui/demo.json.
// Uso: node pruebas/interfaz.mjs   (necesita Playwright; PLAYWRIGHT=/ruta/a/playwright si no está instalado aquí)
// Revisa: 1) ninguna vista tira errores de JavaScript (español e inglés, claro y oscuro, escritorio y celular);
// 2) todo texto tiene traducción en ui/idiomas/en.json; 3) los casos compartidos de pruebas/casos.json (misma lógica que Python);
// 4) el contraste del botón principal; 5) nada se sale de la pantalla a ancho de celular. Con CAPTURAS=carpeta guarda capturas.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT || "playwright");
const CAPTURAS = process.env.CAPTURAS || "";
const errores = [];
const falla = (m) => { errores.push(m); console.log("  ✗ " + m); };
const tipos = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml" };
const servidor = http.createServer((q, r) => {
  const ruta = path.join(RAIZ, "ui", decodeURIComponent(new URL(q.url, "http://x").pathname));
  if (!ruta.startsWith(path.join(RAIZ, "ui")) || !fs.existsSync(ruta) || fs.statSync(ruta).isDirectory()) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { "Content-Type": tipos[path.extname(ruta)] || "application/octet-stream" });
  fs.createReadStream(ruta).pipe(r);
}).listen(0);
const BASE = `http://localhost:${servidor.address().port}/index.html`;
const demo = fs.readFileSync(path.join(RAIZ, "ui", "demo.json"), "utf8");
const casos = JSON.parse(fs.readFileSync(path.join(RAIZ, "pruebas", "casos.json"), "utf8"));
// Textos que vienen de los datos (descripciones, nombres de IA y de categorías) o que no se traducen.
const esDato = (t) => demo.includes(t) || /^(Alcancía|Claude|ChatGPT \(Codex\)|Gemini|English|Español|CLP|USD)$/.test(t);

const EDITOR = "{nombre:'Crédito hipotecario',tipo:'deuda',signo:'gasto',monto:500000,moneda:'CLP',frecuencia:'mensual',dia:15,fecha:'2026-10-18',categoria:'casa',buscar:['DIVIDENDO'],buscarTexto:'DIVIDENDO',cuotas_total:240,cuotas_pagadas:53,desde:'2026-10-18',activo:true,origen:'ia'}";
const CONECTORES = JSON.parse(fs.readFileSync(path.join(RAIZ, "ui", "demo.json"), "utf8")).conectores || [];
const VISTAS = [
  ["resumen", "E=>{E.vista='resumen'}"],
  ["resumen-queda", "E=>{E.cifra='queda'}"],
  ["resumen-gastaste", "E=>{E.cifra='gastaste'}"],
  ["resumen-tienes", "E=>{E.cifra='tienes'}"],
  ["resumen-debes", "E=>{E.cifra='debes'}"],
  ["resumen-todas-categorias", "E=>{E.cifra='gastaste';E.verTodasCat=true;E.compararAbierto=true}"],
  ["resumen-mes-pasado", "E=>{E.mes='2026-09';E.verTodasCat=false}"],
  ["resumen-primer-mes", "E=>{E.mes='2026-05';E.compararAbierto=false}"],
  ["resumen-mes-recien-empezado", "E=>{E.mes='2026-10';E.hoy='2026-10-02'}"],
  ["resumen-hoy", "E=>{E.hoy='2026-10-18'}"],
  ["resumen-saldo-editar", "E=>{E.cifra='tienes';E.saldoEdit={cuenta:'banco-ejemplo',texto:'1000000'}}"],
  ["resumen-saldo-diferencia", "E=>{E.saldoEdit=null;E.saldoAviso={cuadra:false,texto:'x'}}"],
  ["resumen-sin-saldo", "E=>{E.saldoAviso=null;E.cuentas=E.cuentas.map(c=>({...c,saldo:c.id==='banco-ejemplo'?undefined:c.saldo}))}"],
  ["resumen-sin-ningun-saldo", "E=>{E.cuentas=E.cuentas.map(c=>({...c,saldo:undefined}))}"],
  ["movimientos", "E=>{E.vista='movimientos';E.mes='2026-10'}"],
  ["movimientos-aprender", "E=>{E.aprender={contiene:'PAGO PENDIENTE',categoria:'cuentas'}}"],
  ["movimientos-categoria", "E=>{E.aprender={contiene:'CAFE',categoria:'comida',parecidos:3};E.filtro={texto:'',categoria:'comida'}}"],
  ["movimientos-sin-categoria", "E=>{E.aprender=null;E.filtro={texto:'',categoria:'__sin'}}"],
  ["movimientos-detalle", "E=>{E.movVer=E.movimientos.find(m=>m.fecha.startsWith('2026-10')).id}"],
  ["picker", "E=>{E.filtro={texto:'',categoria:''};E.picker={id:E.movimientos.find(m=>!m.categoria).id,buscar:'',nueva:null,hoja:false,top:140,left:300,alto:400}}"],
  ["picker-buscar", "E=>{E.picker.buscar='Cine'}"],
  ["picker-nueva", "E=>{E.picker.nueva={nombre:'Comida atípica',emoji:'',error:''}}"],
  ["picker-hoja", "E=>{E.picker.nueva=null;E.picker.buscar='';E.picker.hoja=true}"],
  ["ordenar", "E=>{E.picker=null;E.vista='ordenar';E.ordenar={i:0,buscar:'',nueva:null}}"],
  ["ordenar-nueva", "E=>{E.ordenar.nueva={nombre:'',emoji:'',error:'Ponle un nombre.'}}"],
  ["ordenar-saltados", "E=>{E.ordenar={i:99,buscar:'',nueva:null}}"],
  ["movimientos-filtro", "E=>{E.vista='movimientos';E.aprender=null;E.filtro={texto:'zzz',categoria:''}}"],
  ["mas", "E=>{E.movVer=null;E.filtro={texto:'',categoria:''};E.vista='mas'}"],
  ["presupuesto", "E=>{E.vista='presupuesto'}"],
  ["consejos", "E=>{E.vista='consejos'}"],
  ["consejos-pidiendo", "E=>{E.pidiendoConsejos=true}"],
  ["consejos-vacio", "E=>{E.pidiendoConsejos=false;E.consejos=[];E.errorConsejos='x'}"],
  ["compromisos", "E=>{E.pidiendoConsejos=false;E.errorConsejos='';E.vista='compromisos';E.mes='2026-10'}"],
  ["compromisos-todas-sugerencias", "E=>{E.sugTodas=true}"],
  ["compromisos-editor-ia", `E=>{E.compEdit={c:${EDITOR},origen:'ia',error:''}}`],
  ["compromisos-editor-error", "E=>{E.compEdit.error='Falta el monto.';E.compEdit.c.frecuencia='semanal';E.compEdit.c.dia=3}"],
  ["compromisos-editor-anual", "E=>{E.compEdit.error='';E.compEdit.c.frecuencia='anual';E.compEdit.c.fecha='2026-03-31';E.compEdit.c.tipo='suscripcion'}"],
  ["compromisos-editar-existente", "E=>{const c=E.compromisos.compromisos[1];E.compEdit={c:{...c,buscarTexto:c.buscar.join(', ')},origen:'manual',error:''}}"],
  ["agregar", "E=>{E.compEdit=null;E.agregar='menu'}"],
  ["compromisos-ia-pidiendo", "E=>{E.agregar='contar';E.compTexto='el arriendo vence el 5, son 450.000';E.compIA={pidiendo:true,error:''}}"],
  ["compromisos-ia-error", "E=>{E.compIA={pidiendo:false,error:'x'}}"],
  ["compromisos-sin-ia", "E=>{E.compIA={pidiendo:false,error:''};E.config.ia=''}"],
  ["compromisos-mes-pasado", "E=>{E.agregar=null;E.config.ia='claude';E.mes='2026-09';E.sugTodas=false}"],
  ["compromisos-con-pausado-y-cuotas", "E=>{E.mes='2026-10';E.compromisos.compromisos.push({id:'c-pausa00001',nombre:'Gimnasio',tipo:'otro',signo:'gasto',monto:25000,moneda:'CLP',frecuencia:'semanal',dia:2,categoria:'ocio',buscar:[],tolerancia:5,activo:false,desde:'2026-10-01',origen:'manual',pagos:{}},{id:'c-deuda00001',nombre:'Crédito de consumo',tipo:'deuda',signo:'gasto',monto:64500,moneda:'CLP',frecuencia:'mensual',dia:9,categoria:'',buscar:['CREDITO CONSUMO'],tolerancia:5,activo:true,desde:'2026-10-01',origen:'detectado',pagos:{},saldo:1200000})}"],
  ["compromisos-aprox-y-uf", "E=>{E.compEdit=null;E.vista='compromisos';E.mes='2026-10'}"],
  ["compromisos-editor-aprox", `E=>{E.compEdit={c:{...${EDITOR},tipo:'cuenta',nombre:'Luz',monto:32000,aproxActivo:true,aproxModo:'variacion',aproxVariacion:7},origen:'manual',error:''}}`],
  ["compromisos-editor-rango", "E=>{E.compEdit.c.aproxModo='rango';E.compEdit.c.aproxMin=28000;E.compEdit.c.aproxMax=36000}"],
  ["compromisos-editor-uf", `E=>{E.compEdit={c:{...${EDITOR},moneda:'UF',monto:12.75,preguntar_uf:true,montoPesos:498000,aproxActivo:false},origen:'detectado',error:''}}`],
  ["compromisos-editor-uf-sin-valor", "E=>{E.config.uf=null;E.compromisos.compromisos=E.compromisos.compromisos.filter(c=>c.moneda!=='UF');E._per=undefined}"],
  ["compromisos-uf-sin-valor", "E=>{E.compEdit=null;E.compromisos.compromisos.push({id:'c-ufsin00001',nombre:'Dividendo',tipo:'deuda',signo:'gasto',monto:12.75,moneda:'UF',frecuencia:'mensual',dia:25,categoria:'casa',buscar:['DIVIDENDO'],tolerancia:5,activo:true,desde:'2026-10-01',origen:'manual',pagos:{},cuotas_total:240,cuotas_pagadas:60})}"],
  ["resumen-uf-sin-valor", "E=>{E.vista='resumen';E.cifra='debes'}"],
  ["ajustes-uf", "E=>{E.ajustes=true}"],
  ["ajustes-uf-con-valor", "E=>{E.config.uf={valor:39500,fecha:'2026-10-18',variacion_mensual:1.5}}"],
  ["compromisos-uf-con-valor", "E=>{E.ajustes=false;E.vista='compromisos'}"],
  ["compromisos-prestamo-editor", `E=>{E.config.uf={valor:39500,fecha:'2026-10-18'};E.vista='compromisos';E.compEdit={c:{...${EDITOR},tipo:'prestamo',con:'Mamá',signo:'gasto',prestamoTotal:1000000,cuotas_total:3,prestamoInteres:0,cuotas_pagadas:0,dia:25,moneda:'CLP'},origen:'manual',error:''}}`],
  ["compromisos-prestamo-editor-ingreso", "E=>{E.compEdit.c.signo='ingreso';E.compEdit.c.prestamoInteres=10}"],
  ["compromisos-prestamo-editor-vacio", "E=>{E.compEdit.c.prestamoTotal=0;E.compEdit.error='Falta cuánto es el préstamo en total.'}"],
  ["compromisos-nunca-sin-salida", "E=>{E.compEdit={c:{nombre:'Gimnasio',tipo:'suscripcion',monto:0,moneda:'CLP',frecuencia:'mensual',dia:3,categoria:'',buscar:['GIMNASIO'],buscarTexto:'GIMNASIO',desde:'2026-10-18',activo:true,origen:'ia'},origen:'ia',error:'No entendí todo: El monto tiene que ser un número mayor que cero. Corrígelo aquí y guárdalo.'}}"],
  ["movimientos-agrupados", "E=>{E.compEdit=null;E.vista='movimientos';E.agruparMov=true}"],
  ["movimientos-agrupados-abierto", "E=>{E.grupoMov='SUPERMERCADO DEL BARRIO'}"],
  ["resumen-te-deben", "E=>{E.agruparMov=false;E.grupoMov=null;E.vista='resumen';E.cifra='debes'}"],
  ["presupuesto-maximo", "E=>{E.vista='presupuesto';E.presEdit=null}"],
  ["presupuesto-no-alcanza", "E=>{E.compromisos.compromisos.push({id:'c-grande0001',nombre:'Grande',tipo:'deuda',signo:'gasto',monto:3000000,moneda:'CLP',frecuencia:'mensual',dia:25,categoria:'',buscar:[],tolerancia:5,activo:true,desde:'2026-10-01',origen:'manual',pagos:{}})}"],
  ["presupuesto-sin-ingresos", "E=>{E.compromisos.compromisos=E.compromisos.compromisos.filter(c=>c.tipo!=='ingreso'&&c.id!=='c-grande0001');E.movimientos=E.movimientos.filter(m=>m.monto<0)}"],
  ["periodo-sueldo", "E=>{E.compromisos.compromisos=E.compromisos.compromisos.filter(c=>!['c-pausa00001','c-deuda00001'].includes(c.id));E.config.inicio_mes={modo:'sueldo',dia:25};E.vista='resumen';E.mes='2026-10'}"],
  ["periodo-sueldo-movimientos", "E=>{E.vista='movimientos'}"],
  ["periodo-sueldo-compromisos", "E=>{E.vista='compromisos'}"],
  ["ajustes-tu-mes", "E=>{E.ajustes=true}"],
  ["ajustes-tu-mes-dia", "E=>{E.config.inicio_mes={modo:'dia',dia:1};E.mes='2026-10'}"],
  ["importar", "E=>{E.ajustes=false;E.vista='resumen';E.importar={paso:'elegir',ia:true}}"],
  ["importar-leyendo", "E=>{E.importar={paso:'leyendo',nombre:'cartola.csv',ia:true}}"],
  ["importar-vista", "E=>{E.importar={paso:'vista',ia:true,vista:{total:41,desde:'2026-10-01',hasta:'2026-10-17',avisos:['x'],receta:{id:'cl-x',nombre:'Banco Ejemplo',institucion:'Banco Ejemplo'},muestra:E.movimientos.slice(0,5)}}}"],
  ["importar-sin-receta", "E=>{E.importar={paso:'sin_receta',nombre:'cartola.xlsx',ia:true,error:'x'}}"],
  ["importar-aprendiendo", "E=>{E.importar.paso='aprendiendo'}"],
  ["importar-receta", "E=>{E.importar={paso:'receta',ia:true,compartir:false,receta:{id:'cl-x'},vista:{total:12,muestra:E.movimientos.slice(0,4)}}}"],
  ["importar-guardando", "E=>{E.importar={paso:'guardando',progreso:{paso:2,total:3,texto:'Guardando sin duplicar…'}}}"],
  ["importar-listo", "E=>{E.importar={paso:'listo',resultado:{nuevos:12,repetidos:29,sin_categoria:2,error_ia:'x'}}}"],
  ["importar-detectados", "E=>{E.importar={paso:'listo',resultado:{nuevos:2,repetidos:0,sin_categoria:0,detectados:E.sugerencias.slice(0,3)},hechos:{1:'no'}}}"],
  ["importar-compromiso", "E=>{const s=E.sugerencias[0];E.importar.paso='compromiso';E.compEdit={c:{...s,buscarTexto:s.buscar.join(', '),desde:E.hoy,activo:true},origen:'detectado',extraido:!!s.cuotas_total,detectado:0,error:''}}"],
  ["importar-compromiso-sin-cuotas", "E=>{E.compEdit.extraido=false;E.compEdit.c.cuotas_total=0}"],
  ["importar-listo-uno", "E=>{E.compEdit=null;E.importar={paso:'listo',resultado:{nuevos:1,repetidos:0,sin_categoria:0}}}"],
  ["importar-error", "E=>{E.importar={paso:'error',error:'x'}}"],
  ["ajustes", "E=>{E.importar=null;E.ajustes=true}"],
  ["ajustes-al-dia", "E=>{E.buscando='alDia'}"],
  ["actualizacion", "E=>{E.ajustes=false;E.vista='resumen';E.actualizacion={hay:true,detalle:'Versión 0.2.0'}}"],
  ["actualizando", "E=>{E.act={paso:'2',texto:'Preparando la versión nueva…',pct:40}}"],
  ["actualizacion-error", "E=>{E.act={paso:'error',texto:'x'}}"],
  ["sin-presupuesto", "E=>{E.act=null;E.actualizacion={hay:false};E.presupuesto={moneda:'CLP',mensual:{}}}"],
  ["conexiones", "E=>{E.vista='conexiones'}"],
  ["conexiones-estados", "E=>{const ids=E.conectores.map(c=>c.id);if(ids[0])E.conexiones[ids[0]]={conectado:true,error:'Mercado Pago no aceptó la llave (puede estar vencida o sin permiso de lectura).'};if(ids[1])E.conexiones[ids[1]]={conectado:true,esperando:true};if(ids[2])E.sincronizando[ids[2]]=true;E.vigilar={activo:true,recientes:[{archivo:'cartola.csv',resultado:'importado',nuevos:1},{archivo:'otra.xlsx',resultado:'sin_receta'}]}}"],
  ["conexiones-otro-pais", "E=>{E.config.pais='US';E.sincronizando={}}"],
  ["conectar-error", "E=>{E.config.pais='CL';E.conectar={id:E.conectores[0].id,campos:{},error:'Falta: x.',enviando:false}}"],
  ["conectar-enviando", "E=>{E.conectar.enviando=true;E.conectar.error=''}"],
  ...CONECTORES.map((c) => [`conectar-${c.id}`, `E=>{E.conectar={id:'${c.id}',campos:{},error:'',enviando:false}}`]),
  ["resumen-al-dia", "E=>{E.conectar=null;E.vista='resumen';E.compromisos.compromisos=E.compromisos.compromisos.filter(c=>c.id==='c-arriendo01')}"],
  ["resumen-sin-compromisos", "E=>{E.compromisos.compromisos=[];E.sugerencias=[];E.cifra='debes'}"],
  ["ordenar-listo", "E=>{E.movimientos.forEach(m=>{if(!m.categoria)m.categoria='otros'});E.vista='ordenar'}"],
  ["vacio", "E=>{E.conectar=null;E.vista='resumen';E.movimientos=[]}"],
];
const navegador = await chromium.launch();

// Lógica compartida con Python (pruebas/casos.json).
{
  const p = await navegador.newPage();
  await p.goto(BASE); await p.waitForFunction(() => window.Alcancia);
  const r = await p.evaluate((c) => {
    const P = window.Alcancia._pruebas, malos = [];
    for (const [v, e] of c.redondear) if (P.redondearArriba(v) !== e) malos.push(`redondear(${v}) = ${P.redondearArriba(v)}`);
    for (const [d, e] of c.regla) if (P.reglaPara(d) !== e) malos.push(`reglaPara(${d}) = ${P.reglaPara(d)}`);
    for (const k of c.resumen) {
      const r = P.resumen(k.movimientos, k.mes, k.hoy, k.presupuesto, c.categorias);
      for (const [campo, esperado] of Object.entries(k.esperado)) if (JSON.stringify(r[campo]) !== JSON.stringify(esperado)) malos.push(`${k.nombre}: ${campo} = ${JSON.stringify(r[campo])}`);
    }
    for (const k of c.historia) {
      const r = P.historia(k.movimientos, k.mes, k.hoy, k.presupuesto, c.categorias, k.categoria ?? null, k.n ?? 6);
      if (JSON.stringify(r) !== JSON.stringify(k.esperado)) malos.push(`${k.nombre}: historia = ${JSON.stringify(r)}`);
    }
    // Igual sin importar el orden de las llaves (Python y JS arman los objetos en distinto orden).
    const canon = (v) => (Array.isArray(v) ? `[${v.map(canon).join(",")}]` : v && typeof v === "object"
      ? `{${Object.keys(v).sort().map((k) => JSON.stringify(k) + ":" + canon(v[k])).join(",")}}` : JSON.stringify(v));
    const comp = c.compromisos;
    const delCaso = (k) => [comp.compromisos.filter((x) => !k.compromisos_ids || k.compromisos_ids.includes(x.id)).concat(k.extra || []),
      comp.movimientos.filter((m) => !k.movimientos_ids || k.movimientos_ids.includes(m.id))];
    for (const k of comp.estado) {
      const [cs, ms] = delCaso(k), r = P.estadoCompromisos(cs, ms, k.mes, k.hoy, k.moneda);
      if (canon(r) !== canon(k.esperado)) malos.push(`compromisos «${k.nombre}» = ${canon(r).slice(0, 600)}`);
    }
    for (const k of comp.gasto_maximo) {
      const [cs, ms] = delCaso(k), r = P.gastoMaximo(ms, cs, k.mes, k.hoy, comp.categorias, k.meses_completos, k.moneda);
      if (canon(r) !== canon(k.esperado)) malos.push(`gasto máximo «${k.nombre}» = ${canon(r)}`);
    }
    const per = c.periodos;
    for (const k of per.rango) if (canon(P.rango(k.mes, k.per)) !== canon(k.esperado)) malos.push(`periodo «${k.nombre}» = ${P.rango(k.mes, k.per)}`);
    for (const k of per.periodo_de) if (P.periodoDe(k.fecha, k.per) !== k.esperado) malos.push(`periodoDe(${k.fecha}) = ${P.periodoDe(k.fecha, k.per)}`);
    const s = per.sueldo, ps = P.periodoConfig(s.inicio_mes, [s.compromiso], s.movimientos, s.hoy, "CLP");
    if (canon(ps) !== canon(s.esperado_per)) malos.push(`periodo con sueldo = ${canon(ps)}`);
    else {
      const mes = P.periodoDe(s.hoy, ps), r = P.resumen(s.movimientos, mes, s.hoy, s.presupuesto, s.categorias, ps);
      if (mes !== s.esperado_periodo) malos.push(`periodo de hoy = ${mes}`);
      for (const [x, v] of Object.entries(s.esperado_resumen)) if (canon(r[x]) !== canon(v)) malos.push(`resumen del periodo: ${x} = ${canon(r[x])}`);
      if (canon(P.historia(s.movimientos, mes, s.hoy, s.presupuesto, s.categorias, null, 3, ps)) !== canon(s.esperado_historia)) malos.push("historia por periodos distinta");
      const e = P.estadoCompromisos([s.compromiso], s.movimientos, mes, s.hoy, "CLP", ps); delete e.compromisos;
      if (canon(e) !== canon(s.esperado_compromisos)) malos.push(`compromisos del periodo = ${canon(e)}`);
    }
    const tc = c.tres_cifras;
    for (const k of tc.casos) {
      const g = P.resumen(tc.movimientos, k.mes, k.hoy, tc.presupuesto, tc.categorias);
      for (const [x, v] of Object.entries(k.esperado.resumen)) if (canon(g[x]) !== canon(v)) malos.push(`tres cifras «${k.nombre}»: resumen.${x} = ${canon(g[x])}`);
      const t = P.loQueTienes(tc.cuentas, tc.movimientos, "CLP");
      if (canon(t) !== canon(k.esperado.tienes)) malos.push(`tres cifras «${k.nombre}»: lo que tienes = ${canon(t)}`);
      const d = P.loQueDebes(tc.compromisos, tc.movimientos, k.hoy, "CLP");
      if (canon(d) !== canon(k.esperado.debes)) malos.push(`tres cifras «${k.nombre}»: lo que debes = ${canon(d)}`);
    }
    // El sueldo: detectarlo, días hábiles y el próximo sueldo.
    const su = c.sueldo;
    for (const k of su.detectar) { const r = P.detectarSueldo(k.movimientos, k.hoy, su.categorias, "CLP"); if (canon(r) !== canon(k.esperado)) malos.push(`detectarSueldo «${k.nombre}» = ${canon(r)}`); }
    for (const k of su.proximo) { const r = P.proximoSueldo(k.per, k.hoy, k.pais === "CL" ? su.feriados_cl : []); if (canon(r) !== canon(k.esperado)) malos.push(`proximoSueldo «${k.nombre}» = ${canon(r)}`); }
    for (const k of su.rango) if (canon(P.rango(k.mes, k.per)) !== canon(k.esperado)) malos.push(`sueldo: rango «${k.nombre}» = ${P.rango(k.mes, k.per)}`);
    for (const k of su.periodo_de) if (P.periodoDe(k.fecha, k.per) !== k.esperado) malos.push(`sueldo: periodoDe(${k.fecha}) = ${P.periodoDe(k.fecha, k.per)}`);
    for (const k of su.regla) if (P.reglaHabil(k.dia, k.llegadas, su.feriados_cl) !== k.esperado) malos.push(`reglaHabil(${k.llegadas}) = ${P.reglaHabil(k.dia, k.llegadas, su.feriados_cl)}`);
    // Interés por mora de un pago atrasado.
    const mo = c.mora;
    for (const k of mo.estado) { const r = P.estadoCompromisos(mo.compromisos, mo.movimientos, k.mes, k.hoy, "CLP", null, null, mo.palabras); if (canon(r) !== canon(k.esperado)) malos.push(`mora «${k.nombre}» = ${canon(r).slice(0, 700)}`); }
    if (P.moraDelAnio(mo.compromisos, mo.movimientos, mo.anio.hoy, "CLP", null, mo.palabras) !== mo.anio.esperado) malos.push(`moraDelAnio = ${P.moraDelAnio(mo.compromisos, mo.movimientos, mo.anio.hoy, "CLP", null, mo.palabras)}`);
    // Préstamos entre personas.
    const pr = c.prestamos;
    for (const [t, n, i, m, esp] of pr.calcular) if (canon(P.calcularPrestamo(t, n, i, m)) !== canon(esp)) malos.push(`calcularPrestamo(${t}, ${n}, ${i}, ${m}) = ${canon(P.calcularPrestamo(t, n, i, m))}`);
    if (canon(P.estadoCompromisos(pr.compromisos, pr.movimientos, pr.estado.mes, pr.estado.hoy, "CLP")) !== canon(pr.estado.esperado)) malos.push("préstamos: estado distinto");
    if (canon(P.loQueDebes(pr.compromisos, pr.movimientos, pr.debes.hoy, "CLP")) !== canon(pr.debes.esperado)) malos.push(`préstamos: lo que debes = ${canon(P.loQueDebes(pr.compromisos, pr.movimientos, pr.debes.hoy, "CLP")).slice(0, 500)}`);
    // Montos aproximados y en UF.
    const ap = c.aproximados;
    for (const k of ap.estado) {
      const cs = ap.compromisos.filter((x) => !k.compromisos_ids || k.compromisos_ids.includes(x.id));
      const r = P.estadoCompromisos(cs, ap.movimientos, k.mes, k.hoy, k.moneda, null, k.uf);
      if (canon(r) !== canon(k.esperado)) malos.push(`aproximados «${k.nombre}» = ${canon(r).slice(0, 700)}`);
    }
    for (const k of ap.gasto_maximo) {
      const r = P.gastoMaximo(ap.movimientos, ap.compromisos, k.mes, k.hoy, ap.categorias, k.meses_completos, k.moneda, null, k.uf);
      if (canon(r) !== canon(k.esperado)) malos.push(`aproximados «${k.nombre}» = ${canon(r)}`);
    }
    for (const k of ap.debes) {
      const r = P.loQueDebes(ap.compromisos, ap.movimientos, k.hoy, k.moneda, null, k.uf);
      if (canon(r) !== canon(k.esperado)) malos.push(`aproximados «${k.nombre}» = ${canon(r).slice(0, 700)}`);
    }
    return malos;
  }, casos);
  r.forEach((m) => falla("lógica distinta a Python: " + m));
  if (!r.length) console.log("  ✓ Misma lógica que Python (pruebas/casos.json)");
  await p.close();
}

for (const [idioma, consulta] of [["español", "idioma=es"], ["inglés", "idioma=en"]]) {
  for (const [modo, opciones] of [["escritorio", { viewport: { width: 1200, height: 820 } }], ["celular", { viewport: { width: 390, height: 844 }, colorScheme: "dark" }]]) {
    for (const bv of [false, true]) {
      const p = await navegador.newPage(opciones);
      p.on("pageerror", (e) => falla(`error de JavaScript (${idioma}, ${modo}): ${e.message}`));
      await p.addInitScript(() => { window._faltantes = new Set(); });
      await p.goto(BASE + "?" + [consulta, bv ? "bienvenida" : ""].filter(Boolean).join("&"));
      await p.waitForFunction(() => window.Alcancia && document.querySelector(".app"));
      const pasos = bv ? [0, 1, 2, 3, 4, 5].map((n) => [`bienvenida-${n}`, `E=>{E.bv=${n}}`]) : VISTAS;
      for (const [nombre, f] of pasos) {
        await p.evaluate(`window.Alcancia._probar(${f})`);
        await p.waitForTimeout(60);
        if (modo === "celular") {
          const ancho = await p.evaluate(() => document.documentElement.scrollWidth);
          if (ancho > 392) falla(`se sale de la pantalla a ancho de celular (${ancho}px) en «${nombre}» (${idioma})`);
        }
        if (CAPTURAS && (idioma === "español" || modo === "escritorio")) await p.screenshot({ path: path.join(CAPTURAS, `${idioma}-${modo}-${nombre}.png`) });
      }
      if (idioma === "inglés") {
        const faltan = [...new Set(await p.evaluate(() => [...window._faltantes]))].filter((t) => !esDato(t));
        if (faltan.length) falla(`${faltan.length} textos sin traducción en ui/idiomas/en.json:\n      ` + faltan.map((t) => JSON.stringify(t)).join("\n      "));
      }
      await p.close();
    }
  }
  console.log(`  ✓ Vistas en ${idioma}`);
}

// Primer uso: lo primero es elegir el idioma, antes de cualquier otra pregunta. Se prueba con un puente falso que anota lo que
// la interfaz le manda a la app (como haría la app de escritorio) para revisar que se guarde idioma_ui y que nada se pida antes.
for (const [locale, sugerido] of [["es-CL", "es"], ["en-US", "en"]]) {
  const p = await navegador.newPage({ locale, viewport: { width: 1200, height: 820 } });
  p.on("pageerror", (e) => falla(`error de JavaScript (idioma, ${locale}): ${e.message}`));
  await p.addInitScript(() => {
    window._enviados = [];
    window.alcanciaEscritorio = { enviar(m) {
      window._enviados.push(m);
      if (m.accion === "listo") fetch("demo.json").then((r) => r.json()).then((d) => { d.config.bienvenida = false; d.config.idioma_ui = ""; window.Alcancia.estado(d); });
    } };
  });
  await p.goto(BASE + "?bienvenida");
  await p.waitForSelector(".dialogo #t-bv");
  const primera = await p.evaluate(() => ({
    titulo: document.querySelector("#t-bv").textContent.replace(/\s+/g, " ").trim(),
    opciones: [...document.querySelectorAll("[data-idioma-bv]")].map((b) => b.dataset.idiomaBv),
    foco: document.activeElement?.id || "",
  }));
  if (primera.titulo !== "Elige tu idioma · Choose your language") falla(`la primera pantalla de la bienvenida no es la de idioma («${primera.titulo}»)`);
  if (primera.opciones.join() !== "es,en") falla(`la pantalla de idioma debe ofrecer Español y English (hay: ${primera.opciones.join()})`);
  if (primera.foco !== `bv-idioma-${sugerido}`) falla(`con el equipo en ${locale} el foco debe partir en «${sugerido}» (está en «${primera.foco}»)`);
  // Con teclado: ir a English (Tab si el sugerido es Español) y elegir con Enter.
  if (sugerido === "es") await p.keyboard.press("Tab");
  await p.keyboard.press("Enter");
  await p.waitForFunction(() => document.documentElement.lang === "en" && !document.querySelector("[data-idioma-bv]"));
  const despues = await p.evaluate(() => ({
    titulo: document.querySelector("#t-bv")?.textContent.trim(),
    boton: document.querySelector(".dialogo .boton.principal")?.textContent.trim(),
    enviados: window._enviados.map((m) => m.accion),
    config: window._enviados.find((m) => m.accion === "config")?.datos,
  }));
  if (despues.titulo !== "Hi, this is Alcancía") falla(`después de elegir English el siguiente paso debe salir en inglés («${despues.titulo}»)`);
  if (despues.boton !== "Next") falla(`los botones de la bienvenida deben salir en inglés («${despues.boton}»)`);
  if (despues.config?.idioma_ui !== "en") falla(`elegir English debe guardar idioma_ui = "en" (se mandó ${JSON.stringify(despues.config)})`);
  if (despues.enviados.slice(0, 2).join() !== "listo,config") falla(`antes de elegir el idioma la interfaz no debe pedir nada más (mandó: ${despues.enviados.join(", ")})`);
  // «Back» vuelve a la pantalla de idioma.
  await p.click(".dialogo [data-bv='0']");
  if (!(await p.$("[data-idioma-bv='es']"))) falla("«Atrás» desde el saludo debe volver a la pantalla de idioma");
  await p.close();
}
{
  // Quien ya hizo la bienvenida no la repite.
  const p = await navegador.newPage();
  await p.goto(BASE); await p.waitForSelector(".app");
  if (await p.$("[data-idioma-bv], .dialogo")) falla("la bienvenida (ni la pantalla de idioma) no debe aparecer si ya se hizo");
  await p.close();
}
console.log("  ✓ Primer uso: lo primero es el idioma, se guarda y la bienvenida sigue en ese idioma");

// Compromisos de punta a punta con la simulación: la tarjeta «Por pagar», «Ya lo pagué», agregar con tus palabras, el gasto
// máximo y lo que se detecta al importar una cartola (con las preguntas que siguen). En español e inglés, escritorio y celular.
const TEXTOS_COMP = {
  español: { atrasado: "vencido hace 8 días", pronto: "Vence en 2 días", pronto2: "vence en 2 días", maximo: "puedes gastar hasta", cuota: "cuota 4 de 24", agregado: "Agregado" },
  inglés: { atrasado: "8 days overdue", pronto: "Due in 2 days", pronto2: "due in 2 days", maximo: "you can spend up to", cuota: "installment 4 of 24", agregado: "Added" },
};
for (const [idioma, consulta] of [["español", "idioma=es"], ["inglés", "idioma=en"]]) {
  for (const [modo, opciones] of [["escritorio", { viewport: { width: 1200, height: 820 } }], ["celular", { viewport: { width: 390, height: 844 }, colorScheme: "dark" }]]) {
    const t = TEXTOS_COMP[idioma], donde = `(${idioma}, ${modo})`;
    const p = await navegador.newPage(opciones);
    p.on("pageerror", (e) => falla(`error de JavaScript en compromisos ${donde}: ${e.message}`));
    const ancho = async (paso) => { if (modo === "celular" && (await p.evaluate(() => document.documentElement.scrollWidth)) > 392) falla(`se sale de la pantalla en «${paso}» ${donde}`); };
    const texto = (sel) => p.$eval(sel, (el) => el.textContent.replace(/\s+/g, " "));
    await p.goto(BASE + "?" + consulta);
    // Lo primero que se lee: lo que falta pagar (lo atrasado primero).
    await p.waitForSelector(".al-dia.atrasado");
    const alDia = await texto(".al-dia");
    if (!alDia.includes("Plan de celular") || !alDia.includes(t.atrasado)) falla(`arriba debe decir que falta pagar el plan de celular, atrasado ${donde}: ${alDia.slice(0, 200)}`);
    // El desglose de «Lo que debes» trae todo lo que falta este mes.
    await p.click('[data-cifra="debes"]');
    let porPagar = await texto(".por-pagar");
    if (!porPagar.includes("Crédito automotriz") || !porPagar.includes(t.pronto)) falla(`«Lo que debes» debe mostrar el crédito que vence en 2 días ${donde}`);
    if (porPagar.includes("Arriendo")) falla(`el arriendo ya se reconoció pagado: no va en lo que debes ${donde}`);
    const atrasadoPrimero = await p.$eval(".por-pagar .comp-fila", (el) => el.classList.contains("atrasado"));
    if (!atrasadoPrimero) falla(`lo atrasado va primero en «Lo que debes» ${donde}`);
    await ancho("por pagar");
    await p.click(".al-dia [data-comp-pagado]");
    porPagar = await texto(".por-pagar");
    if (porPagar.includes("Plan de celular")) falla(`«Ya lo pagué» debe sacarlo de lo que debes ${donde}`);
    if (!(await texto(".al-dia")).includes(t.pronto2)) falla(`después de pagarlo, arriba sale lo siguiente que vence ${donde}`);
    // Agregar con tus palabras (la simulación hace de IA) y confirmar la tarjeta.
    await p.click('.nav [data-vista="compromisos"]');
    // Agregar un pago va en «+»: la acción única para agregar, con su hoja (cartola, pago que se repite o conectar).
    await p.click(".nav-agregar");
    if ((await p.$$(".dialogo .opcion-agregar")).length !== 3) falla(`«+» ofrece cartola, pago que se repite y conectar ${donde}`);
    await ancho("agregar");
    await p.click('.dialogo .opcion-agregar[data-accion="agregar-contar"]');
    await p.fill("#comp-texto", "el arriendo de la bodega vence el 5 de cada mes, son 85.000");
    await p.click('[data-accion="comp-entender"]');
    await p.waitForSelector("#editor-comp #ce-nombre");
    const editor = await p.evaluate(() => ({ monto: document.querySelector("#ce-monto").value.replace(/\D/g, ""), dia: document.querySelector("#ce-dia").value,
      nombre: document.querySelector("#ce-nombre").value }));
    if (editor.monto !== "85000" || editor.dia !== "5") falla(`la tarjeta editable debe traer monto y día ${donde}: ${JSON.stringify(editor)}`);
    await ancho("editor");
    await p.fill("#ce-nombre", "Bodega");
    await p.click('[data-accion="comp-guardar"]');
    await p.waitForFunction(() => !document.querySelector("#editor-comp"));
    if (!(await texto(".contenido")).includes("Bodega")) falla(`el compromiso nuevo debe aparecer en la lista ${donde}`);
    await ancho("compromisos");
    // Gasto máximo en Presupuesto.
    await p.click('.nav [data-vista="mas"]');
    await p.click('.lista-mas [data-vista="presupuesto"]');
    if (!(await texto(".maximo")).includes(t.maximo)) falla(`Presupuesto debe decir cuánto se puede gastar en lo variable ${donde}`);
    await ancho("gasto máximo");
    // Importar: lo detectado y las preguntas que siguen (la cuota sale de la cartola y no se pregunta).
    await p.click(".nav-agregar");
    await p.click('.dialogo .opcion-agregar[data-accion="importar"]');
    await p.click('[data-accion="elegir-cartola"]');
    await p.click('[data-accion="importar-guardar"]');
    await p.waitForSelector(".detectados [data-det-agregar]", { timeout: 8000 });
    await ancho("detectados");
    await p.click(".detectados [data-det-agregar]");
    await p.waitForSelector(".dialogo #ce-nombre");
    const dialogo = await texto(".dialogo");
    if (!dialogo.toLowerCase().includes(t.cuota)) falla(`la cuota sacada de la cartola debe verse ${donde}`);
    if (await p.$(".dialogo #ce-cuotas_total")) falla(`si la cartola trae la cuota, no se pregunta ${donde}`);
    await ancho("preguntas tras importar");
    await p.click('.dialogo [data-accion="comp-guardar"]');
    await p.waitForSelector(".detectados .ok-txt");
    if (!(await texto(".detectados")).includes(t.agregado)) falla(`tras guardar, el detectado queda como agregado ${donde}`);
    await p.close();
  }
}
console.log("  ✓ Compromisos: por pagar, ya lo pagué, agregar con tus palabras, gasto máximo y lo detectado al importar");

// Resumen simple y categorizar rápido: las tres cifras, poner categoría en dos toques, crear una al vuelo, aprender la regla,
// corregir el saldo (y que diga la diferencia) y «Por ordenar» con el teclado. En español e inglés, escritorio y celular.
const TEXTOS_SIMPLE = {
  español: { tienes: "Lo que tienes", gasto: "Lo que gastaste", debes: "Lo que debes", queda: "Te quedan", dias: "días ·", aprendi: "Aprendí esto de tus movimientos", diferencia: "Había una diferencia de", nueva: "Comida atípica", de: "de" },
  inglés: { tienes: "What you have", gasto: "What you spent", debes: "What you owe", queda: "You have", dias: "days ·", aprendi: "I learned this from your transactions", diferencia: "There was a difference of", nueva: "Comida atípica", de: "of" },
};
for (const [idioma, consulta] of [["español", "idioma=es"], ["inglés", "idioma=en"]]) {
  for (const [modo, opciones] of [["escritorio", { viewport: { width: 1200, height: 820 } }], ["celular", { viewport: { width: 390, height: 844 }, colorScheme: "dark" }]]) {
    const t = TEXTOS_SIMPLE[idioma], donde = `(${idioma}, ${modo})`;
    const p = await navegador.newPage(opciones);
    p.on("pageerror", (e) => falla(`error de JavaScript en el resumen simple ${donde}: ${e.message}`));
    const ancho = async (paso) => { if (modo === "celular" && (await p.evaluate(() => document.documentElement.scrollWidth)) > 392) falla(`se sale de la pantalla en «${paso}» ${donde}`); };
    const texto = (sel) => p.$eval(sel, (el) => el.textContent.replace(/\s+/g, " "));
    await p.goto(BASE + "?" + consulta);
    await p.waitForSelector(".tres");
    const filas = await p.$$eval(".cifra-fila", (l) => l.map((x) => ({ id: x.dataset.cifra, t: x.textContent.replace(/\s+/g, " ") })));
    if (filas.map((f) => f.id).join() !== "tienes,gastaste,debes") falla(`el resumen debe mostrar las tres cifras en orden ${donde}: ${filas.map((f) => f.id)}`);
    if (!filas[0].t.includes(t.tienes) || !filas[1].t.includes(t.gasto) || !filas[2].t.includes(t.debes)) falla(`las tres cifras con palabras simples ${donde}: ${filas.map((f) => f.t.slice(0, 40)).join(" | ")}`);
    if (!filas[0].t.replace(/\D/g, "").includes("1021090")) falla(`«Lo que tienes» suma los saldos (612.000 anotado + movimientos, y 84.300 que informa la billetera) ${donde}: ${filas[0].t}`);
    // En la fila, lo de este mes (incluye el seguro de salud en UF, ≈ 72.900, por eso va con «≈»); el total va en el desglose.
    if (!filas[2].t.replace(/\D/g, "").includes("534870") || !filas[2].t.includes("≈")) falla(`«Lo que debes» muestra lo de este mes ${donde}: ${filas[2].t}`);
    // La cifra protagonista arriba: cuánto te queda (lo que tienes − lo que falta pagar este mes), los días y cuánto da por día.
    const heroe = await texto(".heroe");
    if (!heroe.includes(t.queda) || !heroe.includes(t.dias) || !heroe.replace(/\D/g, "").includes("592100")) falla(`la cifra protagonista dice cuánto te queda (1.021.090 − 428.990) ${donde}: ${heroe}`);
    if (await p.$(".resumen-simple .codigo-moneda")) falla(`con una sola moneda no se repite «CLP» junto a cada cifra ${donde}`);
    const primero = await p.evaluate(() => { const h = document.querySelector(".heroe").getBoundingClientRect(), t = document.querySelector(".tres").getBoundingClientRect(); return h.top < t.top && h.left <= t.left + 1; });
    if (!primero) falla(`la cifra protagonista va arriba a la izquierda, antes de las tres cifras ${donde}`);
    await p.click('[data-cifra="queda"]');
    const calculo = (await texto("#desglose")).replace(/[.,]/g, "");
    if (!calculo.includes("1021090") || !calculo.includes("428990")) falla(`al tocar la cifra se explica el cálculo ${donde}: ${calculo.slice(0, 300)}`);
    await p.click('[data-cifra="queda"]');
    if (await p.$("#desglose")) falla(`tocar otra vez la cifra cierra la explicación ${donde}`);
    if (!(await texto(".aprendi")).includes(t.aprendi)) falla(`el resumen muestra lo que aprendió de los movimientos ${donde}`);
    await ancho("tres cifras");
    // «Lo que debes»: cuotas que quedan de la lavadora (3 de 61.000) y lo de la tarjeta desde el último pago.
    await p.click('[data-cifra="debes"]');
    const debes = (await texto("#desglose")).replace(/[.,]/g, "");
    if (!debes.includes("Tienda Electro · Lavadora") || !debes.includes("183000") || !debes.includes("106980")) falla(`el desglose de lo que debes trae cuotas y tarjeta ${donde}: ${debes.slice(0, 300)}`);
    // Lo que queda del préstamo de la mamá (6 de 8 cuotas de 150.000) y el resto: el total de deudas va en el desglose.
    if (!debes.includes("5874850")) falla(`el desglose trae el total de lo que debes ${donde}: ${debes.slice(0, 300)}`);
    // Corregir el saldo: si no cuadra, lo dice.
    await p.click('[data-cifra="tienes"]');
    await p.click('[data-saldo-editar="banco-ejemplo"]');
    await p.fill("#saldo-banco-ejemplo", "936200");
    await p.press("#saldo-banco-ejemplo", "Enter");
    const aviso = await texto(".saldo-aviso");
    if (!aviso.includes(t.diferencia) || !aviso.replace(/\D/g, "").includes("590")) falla(`al corregir el saldo dice la diferencia (590) ${donde}: ${aviso}`);
    await ancho("saldo");
    // Dos toques: el chip y la categoría.
    await p.click('.nav [data-vista="movimientos"]');
    // Nombres legibles: sin asteriscos ni mayúsculas gritadas; el original aparece al tocar.
    const nombres = await p.$$eval(".mov .t", (l) => l.map((x) => x.textContent));
    if (nombres.some((n) => n.includes("*")) || !nombres.includes("Delivery Rapidito")) falla(`los comercios se muestran legibles ${donde}: ${nombres.slice(0, 5)}`);
    await p.click(".mov .mov-txt");
    if (!(await p.$(".mov-detalle"))) falla(`tocar un movimiento muestra su descripción original ${donde}`);
    await p.click(".mov .mov-txt");
    const id1 = await p.$eval(".mov .chip-cat.falta", (el) => el.dataset.elegir);
    await p.click(`#chip-${id1}`);
    await p.waitForSelector(".picker [data-pick]");
    await ancho("panel de categorías");
    await p.click('.picker [data-pick="ocio"]');
    const cat1 = await p.evaluate((id) => new Promise((r) => window.Alcancia._probar((E) => r(E.movimientos.find((m) => m.id === id).categoria))), id1);
    if (cat1 !== "ocio") falla(`dos toques ponen la categoría ${donde}: ${cat1}`);
    if (await p.$(".picker")) falla(`el panel se cierra al elegir ${donde}`);
    // ¿Siempre para este comercio? → aprende la regla.
    await p.waitForSelector(".aviso-regla");
    await p.click('.aviso-regla [data-accion="aprender-si"]');
    const reglas = await p.evaluate(() => new Promise((r) => window.Alcancia._probar((E) => r(E.reglas.map((x) => x.categoria)))));
    if (!reglas.includes("ocio")) falla(`«Sí, siempre» aprende la regla ${donde}`);
    // Crear una categoría al vuelo («Comida atípica») desde el buscador.
    const id2 = await p.$eval(".mov .chip-cat.falta", (el) => el.dataset.elegir);
    await p.click(`#chip-${id2}`);
    await p.fill("#picker-buscar", t.nueva);
    await p.click('.picker [data-nueva-cat][data-con-nombre]');
    const nueva = await p.evaluate((id) => new Promise((r) => window.Alcancia._probar((E) => { const c = E.categorias.find((x) => x.nombre === "Comida atípica"); r({ c, m: E.movimientos.find((m) => m.id === id).categoria }); })), id2);
    if (!nueva.c || nueva.c.emoji !== "🍽️" || nueva.m !== nueva.c.id) falla(`crear «Comida atípica» al vuelo (con 🍽️) y ponérsela ${donde}: ${JSON.stringify(nueva)}`);
    if (!(await texto(`#chip-${id2}`)).includes("Comida atípica")) falla(`el chip muestra la categoría nueva sin traducirla ${donde}`);
    await p.keyboard.press("Escape");
    // «Por ordenar» es un filtro de Movimientos (con contador) y un pendiente del Inicio.
    await p.click('[data-accion="filtro-ordenar"]');
    const soloSin = await p.$$eval(".mov", (l) => l.every((x) => x.querySelector(".chip-cat.falta")));
    if (!soloSin) falla(`el filtro «Por ordenar» deja solo los sin categoría ${donde}`);
    await p.click('[data-accion="filtro-ordenar"]');
    // «Por ordenar» con el teclado: 1 elige, → salta.
    await p.click('.nav [data-vista="resumen"]');
    await p.click('.pendientes [data-vista="ordenar"]');
    await p.waitForSelector(".mov-grande");
    const antes = await p.evaluate(() => new Promise((r) => window.Alcancia._probar((E) => r(E.movimientos.filter((m) => !m.categoria).length))));
    await p.keyboard.press("1");
    const despues = await p.evaluate(() => new Promise((r) => window.Alcancia._probar((E) => r(E.movimientos.filter((m) => !m.categoria).length))));
    if (despues !== antes - 1) falla(`en «Por ordenar», la tecla 1 pone la categoría (${antes} → ${despues}) ${donde}`);
    await p.keyboard.press("ArrowRight");
    if (!(await texto(".contador-ordenar")).startsWith("2 ")) falla(`→ salta al siguiente ${donde}: ${await texto(".contador-ordenar")}`);
    await p.keyboard.press("ArrowLeft");
    if (!(await texto(".contador-ordenar")).startsWith("1 ")) falla(`← vuelve ${donde}`);
    await ancho("por ordenar");
    await p.close();
  }
}
console.log("  ✓ Resumen simple: tres cifras, categorizar en dos toques, crear al vuelo, aprender la regla, saldo y «Por ordenar» con teclado");

// Montos aproximados y en UF: la estimación en pesos, marcar «aprox.», la opción UF, Cuéntale con UF y el valor de la UF en Ajustes.
for (const [idioma, consulta] of [["español", "idioma=es"], ["inglés", "idioma=en"]]) {
  for (const [modo, opciones] of [["escritorio", { viewport: { width: 1200, height: 820 } }], ["celular", { viewport: { width: 390, height: 844 }, colorScheme: "dark" }]]) {
    const donde = `(${idioma}, ${modo})`;
    const p = await navegador.newPage(opciones);
    p.on("pageerror", (e) => falla(`error de JavaScript en UF ${donde}: ${e.message}`));
    const ancho = async (paso) => { if (modo === "celular" && (await p.evaluate(() => document.documentElement.scrollWidth)) > 392) falla(`se sale de la pantalla en «${paso}» ${donde}`); };
    const texto = (sel) => p.$eval(sel, (el) => el.textContent.replace(/\s+/g, " "));
    await p.goto(BASE + "?" + consulta);
    await p.waitForSelector(".app");
    await p.click('.nav [data-vista="compromisos"]');
    const seguro = await p.$$eval(".comp-fila", (l) => l.map((x) => x.textContent.replace(/\s+/g, " ")).find((t) => t.includes("Seguro de salud")) || "");
    if (!seguro.includes("1,85 UF ≈") || !seguro.includes("≈ $72.900")) falla(`el compromiso en UF muestra la UF y el rango en pesos ${donde}: ${seguro}`);
    await ancho("compromisos con UF");
    // A mano: «El monto varía (aprox.)» con un porcentaje.
    await p.click('.pie-vista [data-accion="agregar-contar"]');
    await p.click('.dialogo [data-accion="comp-nuevo"]');
    if (!(await p.$$eval("#ce-moneda option", (l) => l.map((o) => o.value))).includes("UF")) falla(`la moneda ofrece «UF» ${donde}`);
    await p.fill("#ce-nombre", "Luz");
    await p.fill("#ce-monto", "32500");  // 32.000 justo es una entrada de concierto de la demo: sin palabras calzaría por monto exacto
    await p.check("[data-ce-aprox]");
    await p.waitForSelector("#ce-aproxVariacion");
    await p.fill("#ce-aproxVariacion", "10");
    await p.press("#ce-aproxVariacion", "Tab");
    await ancho("editor aproximado");
    await p.click('[data-accion="comp-guardar"]');
    await p.waitForFunction(() => !document.querySelector("#editor-comp"));
    const luz = await p.$$eval(".comp-fila", (l) => l.map((x) => x.textContent.replace(/\s+/g, " ")).find((t) => t.includes("Luz")) || "");
    if (!luz.includes("≈ $32.500") || !luz.replace(/\D/g, "").includes("2920035800")) falla(`la luz aproximada se muestra con su rango (29.200 a 35.800) ${donde}: ${luz}`);
    // Cuéntale con UF (la simulación hace de IA).
    await p.click(".nav-agregar");
    await p.click('.dialogo [data-accion="agregar-contar"]');
    await p.fill("#comp-texto", "el dividendo son 12,75 UF los 25");
    await p.click('[data-accion="comp-entender"]');
    await p.waitForSelector("#editor-comp #ce-monto");
    const ed = await p.evaluate(() => ({ moneda: document.querySelector("#ce-moneda").value, monto: document.querySelector("#ce-monto").value }));
    if (ed.moneda !== "UF" || ed.monto !== "12,75") falla(`Cuéntale entiende «12,75 UF» ${donde}: ${JSON.stringify(ed)}`);
    if (!(await texto("#editor-comp")).includes("UF")) falla(`el editor muestra la estimación en UF ${donde}`);
    await ancho("editor UF");
    await p.click('[data-accion="comp-cancelar"]');
    // «Valor de la UF hoy» en Ajustes.
    await p.click('.nav [data-vista="mas"]');
    await p.click('.lista-mas [data-accion="ajustes"]');
    await p.fill("#uf-valor", "39.500");
    await p.press("#uf-valor", "Tab");
    const uf = await p.evaluate(() => { let u; window.Alcancia._probar((E) => { u = E.config.uf; }); return u; });
    if (!uf || uf.valor !== 39500 || !/^\d{4}-\d{2}-\d{2}$/.test(uf.fecha || "")) falla(`el valor de la UF se guarda en Ajustes ${donde}: ${JSON.stringify(uf)}`);
    await ancho("ajustes UF");
    await p.close();
  }
}
console.log("  ✓ Aproximados y UF: rango en pesos, «aprox.» en el editor, Cuéntale con UF y el valor de la UF en Ajustes");

// Préstamos entre personas, Cuéntale que nunca deja sin salida, «Te deben» aparte y agrupar (compromisos y movimientos por comercio).
const TEXTOS_PR = {
  español: { debes: "Le debes $1.800.000 a Tia", cuotas: "Son 12 cuotas de $150.000", grupo: "Créditos y préstamos", te: "te deben", agrupar: "movimiento" },
  inglés: { debes: "You owe $1.800.000 to Tia", cuotas: "12 installments of $150.000", grupo: "Loans and credit", te: "owed to you", agrupar: "transaction" },
};
for (const [idioma, consulta] of [["español", "idioma=es"], ["inglés", "idioma=en"]]) {
  for (const [modo, opciones] of [["escritorio", { viewport: { width: 1200, height: 820 } }], ["celular", { viewport: { width: 390, height: 844 }, colorScheme: "dark" }]]) {
    const t = TEXTOS_PR[idioma], donde = `(${idioma}, ${modo})`;
    const p = await navegador.newPage(opciones);
    p.on("pageerror", (e) => falla(`error de JavaScript en préstamos ${donde}: ${e.message}`));
    const ancho = async (paso) => { if (modo === "celular" && (await p.evaluate(() => document.documentElement.scrollWidth)) > 392) falla(`se sale de la pantalla en «${paso}» ${donde}`); };
    const texto = (sel) => p.$eval(sel, (el) => el.textContent.replace(/\s+/g, " "));
    await p.goto(BASE + "?" + consulta);
    await p.waitForSelector(".app");
    // Resumen: lo que te deben va aparte.
    await p.click('[data-cifra="debes"]');
    if (!(await texto("#desglose")).toLowerCase().includes(t.te)) falla(`«Lo que debes» dice aparte lo que te deben ${donde}`);
    if (!(await texto("#desglose")).replace(/\D/g, "").includes("200000")) falla(`el desglose trae lo que te deben (200.000) ${donde}`);
    // Cuéntale: un préstamo con el monto en palabras; la tarjeta muestra el cálculo en vivo.
    await p.click('.nav [data-vista="compromisos"]');
    await p.click(".nav-agregar");
    await p.click('.dialogo [data-accion="agregar-contar"]');
    await p.fill("#comp-texto", "mi tia me prestó 1,8 millones en 12 meses");
    await p.click('[data-accion="comp-entender"]');
    await p.waitForSelector("#editor-comp #ce-con");
    const ed = await p.evaluate(() => ({ tipo: document.querySelector("#ce-tipo").value, con: document.querySelector("#ce-con").value }));
    if (ed.tipo !== "prestamo" || ed.con !== "Tia") falla(`Cuéntale entiende el préstamo ${donde}: ${JSON.stringify(ed)}`);
    if (!(await texto(".calculo-vivo")).includes(t.cuotas)) falla(`el cálculo en vivo del préstamo ${donde}: ${await texto(".calculo-vivo")}`);
    await ancho("editor de préstamo");
    await p.click('[data-accion="comp-guardar"]');
    await p.waitForFunction(() => !document.querySelector("#editor-comp"));
    if (!(await texto(".contenido")).includes(t.debes)) falla(`«Lo que estás pagando» dice cuánto le debes y a quién ${donde}`);
    if (!(await p.$$eval("h3.grupo.con-total", (l) => l.map((x) => x.textContent))).some((x) => x.includes(t.grupo))) falla(`compromisos agrupados con subtotal ${donde}`);
    await ancho("préstamo guardado");
    // Nunca sin salida: sin monto, igual se abre la tarjeta con lo que se entendió y el error en simple.
    await p.click('.pie-vista [data-accion="agregar-contar"]');
    await p.fill("#comp-texto", "el gimnasio los 3");
    await p.click('[data-accion="comp-entender"]');
    await p.waitForSelector("#editor-comp .error-txt");
    if (!(await p.$eval("#ce-nombre", (el) => el.value)).toLowerCase().includes("gimnasio")) falla(`la tarjeta trae lo que sí se entendió ${donde}`);
    await p.click('[data-accion="comp-cancelar"]');
    // Movimientos agrupados por comercio, con total y cantidad, que se despliegan.
    await p.click('.nav [data-vista="movimientos"]');
    const filas = await p.$$eval(".mov", (l) => l.length);
    await p.click('[data-accion="agrupar-mov"]');
    const grupos = await p.$$eval(".grupo-mov", (l) => l.length);
    if (!grupos || grupos >= filas) falla(`agrupar por comercio junta movimientos (${filas} → ${grupos}) ${donde}`);
    if (!(await texto(".grupo-mov")).includes(t.agrupar)) falla(`cada grupo dice cuántos movimientos tiene ${donde}`);
    await p.click(".grupo-mov");
    if (!(await p.$(".grupo-mov-lista .mov"))) falla(`un grupo se despliega ${donde}`);
    await ancho("movimientos agrupados");
    await p.close();
  }
}
console.log("  ✓ Préstamos: Cuéntale con montos en palabras, cálculo en vivo, «Te deben» aparte, nunca sin salida y agrupar");

// El sueldo: detectado solo si nunca elegiste, el próximo sueldo en día hábil, «¿Aún no te pagan?» y la invitación si no hay sueldo claro.
const TEXTOS_SU = {
  español: { mes: "Tu mes va desde que llegó tu sueldo (5 oct", prox: "Próximo sueldo: jueves 5 de noviembre (aprox.)", detecte: "Lo detecté de tus movimientos",
    invita: "¿Cuándo te pagan?", pregunta: "¿Aún no te pagan? Lo esperaba el jueves 5 de noviembre", cartola: "Agrega tu cartola", es: "¿Es este? Deposito Empresa Ejemplo", hasta: "hasta tu sueldo" },
  inglés: { mes: "Your month runs from when your salary arrived (Oct 5", prox: "Next payday: Thursday, November 5 (approx.)", detecte: "I detected it from your transactions",
    invita: "When do you get paid?", pregunta: "Haven't been paid yet? I expected it on Thursday, November 5", cartola: "Add your statement", es: "Is it this one? Deposito Empresa Ejemplo", hasta: "until payday" },
};
for (const [idioma, consulta] of [["español", "idioma=es"], ["inglés", "idioma=en"]]) {
  for (const [modo, opciones] of [["escritorio", { viewport: { width: 1200, height: 820 } }], ["celular", { viewport: { width: 390, height: 844 }, colorScheme: "dark" }]]) {
    const t = TEXTOS_SU[idioma], donde = `(${idioma}, ${modo})`;
    const p = await navegador.newPage(opciones);
    p.on("pageerror", (e) => falla(`error de JavaScript en sueldo ${donde}: ${e.message}`));
    const ancho = async (paso) => { if (modo === "celular" && (await p.evaluate(() => document.documentElement.scrollWidth)) > 392) falla(`se sale de la pantalla en «${paso}» ${donde}`); };
    const texto = (sel) => p.$eval(sel, (el) => el.textContent.replace(/\s+/g, " ")).catch(() => "");
    /** Manda a la página el estado de la demo cambiado por `f` (como lo mandaría la app). */
    const estado = (f) => { const d = JSON.parse(fs.readFileSync(path.join(RAIZ, "ui", "demo.json"), "utf8")); d.config.bienvenida = true; f(d); return p.evaluate((x) => window.Alcancia.estado(x), d); };
    await p.goto(BASE + "?" + consulta);
    await p.waitForSelector(".app");
    // Nunca eligió: Alcancía usa su sueldo (llega el 5) y lo dice en una línea discreta.
    await estado((d) => { delete d.config.inicio_mes; });
    const cfg = await p.evaluate(() => { let c; window.Alcancia._probar((E) => { c = E.config.inicio_mes; }); return c; });
    if (JSON.stringify(cfg) !== JSON.stringify({ modo: "sueldo", dia: 5, auto: true })) falla(`se usa el sueldo detectado ${donde}: ${JSON.stringify(cfg)}`);
    // Lo que detecté de tu mes va en la explicación de la cifra protagonista (al tocarla).
    if (!(await texto(".heroe")).includes(t.hasta)) falla(`con el sueldo, la cifra dice «hasta tu sueldo» ${donde}: ${await texto(".heroe")}`);
    await p.click('[data-cifra="queda"]');
    if (!(await texto(".linea-mes")).includes(t.mes)) falla(`la línea «Tu mes va desde…» ${donde}: ${await texto(".linea-mes")}`);
    if (!(await texto(".pista-sueldo")).includes(t.prox)) falla(`el próximo sueldo con fecha ${donde}: ${await texto(".pista-sueldo")}`);
    await ancho("tu mes va desde tu sueldo");
    await p.click('.linea-mes [data-accion="ajustes-mes"]');
    if ((await p.evaluate(() => document.activeElement?.id)) !== "inicio-modo") falla(`«Cambiar» lleva a «Tu mes empieza» en Ajustes ${donde}`);
    if (!(await texto(".dialogo")).includes(t.detecte)) falla(`Ajustes dice que lo detectó ${donde}`);
    await p.click('[data-accion="cerrar"]');
    // Lo que la persona eligió no se toca.
    await estado((d) => { d.config.inicio_mes = { modo: 'dia', dia: 1 }; });
    if (await p.$(".linea-mes")) falla(`con el mes elegido no hay línea de sueldo ${donde}`);
    // Sin un sueldo claro: no se inventa; se invita a decir cuándo te pagan.
    await estado((d) => { delete d.config.inicio_mes; d.movimientos = d.movimientos.filter((m) => m.monto < 0); d.compromisos.compromisos = d.compromisos.compromisos.filter((c) => c.tipo !== 'ingreso'); });
    if (!(await texto(".linea-mes")).includes(t.invita)) falla(`sin sueldo claro, la invitación ${donde}`);
    // Se atrasó (esperado el jueves 5 de noviembre, hoy lunes 9): la pregunta suave.
    await estado((d) => { d.hoy = '2026-11-09'; d.config.inicio_mes = { modo: 'sueldo', dia: 5 }; });
    if (!(await texto(".linea-mes.pregunta")).includes(t.pregunta)) falla(`«¿Aún no te pagan?» ${donde}: ${await texto(".linea-mes")}`);
    await ancho("¿aún no te pagan?");
    await p.click('[data-sueldo="no"]');
    if (await p.$(".linea-mes.pregunta")) falla(`«Todavía no» no insiste hoy ${donde}`);
    await estado((d) => { d.hoy = '2026-11-09'; d.config.inicio_mes = { modo: 'sueldo', dia: 5 }; });
    if (await p.$(".linea-mes.pregunta")) falla(`«Todavía no» sigue valiendo hoy ${donde}`);
    await p.evaluate(() => localStorage.clear());
    // «Ya me pagaron» sin movimiento: invita a agregar la cartola o a marcarlo.
    await estado((d) => { d.hoy = '2026-11-09'; d.config.inicio_mes = { modo: 'sueldo', dia: 5 }; });
    await p.click('[data-sueldo="pagaron"]');
    if (!(await texto(".linea-mes.pregunta")).includes(t.cartola)) falla(`«Ya me pagaron» sin movimiento ${donde}: ${await texto(".linea-mes")}`);
    await ancho("ya me pagaron");
    await p.click('[data-sueldo="hoy"]');
    if (await p.$(".linea-mes.pregunta")) falla(`marcado como recibido hoy, ya no pregunta ${donde}`);
    // «Ya me pagaron» con un ingreso que no se reconoció: «¿Es este?» y el periodo parte ese día.
    await estado((d) => { d.hoy = '2026-11-09'; d.config.inicio_mes = { modo: 'sueldo', dia: 5 }; d.movimientos.push({ id: 'nov-sueldo', fecha: '2026-11-06', descripcion: 'DEPOSITO EMPRESA EJEMPLO', monto: 1450000, moneda: 'CLP', cuenta: 'banco-ejemplo', categoria: '' }); });
    await p.click('[data-sueldo="pagaron"]');
    if (!(await texto(".linea-mes.pregunta")).includes(t.es)) falla(`«¿Es este?» con el ingreso más probable ${donde}: ${await texto(".linea-mes")}`);
    await p.click('[data-sueldo="es"]');
    const desde = await p.evaluate(() => { let r; window.Alcancia._probar((E) => { r = E.mes; }); return r; });
    if (desde !== "2026-11") falla(`el periodo pasa al del sueldo ${donde}: ${desde}`);
    if (!(await texto(".selector-mes, .encabezado")).match(/6 (nov|Nov)|Nov 6/)) falla(`el periodo parte el 6 de noviembre ${donde}: ${await texto(".encabezado")}`);
    await ancho("sueldo marcado");
    await p.close();
  }
}
console.log("  ✓ Sueldo: detectado solo, próximo sueldo en día hábil, «¿Aún no te pagan?» y la invitación si no hay sueldo claro");

// Interés por mora: el plan de celular se pagó 7 días tarde con un recargo aparte.
const TEXTOS_MO = {
  español: { pago: "Pagado el 17 oct con 7 días de atraso · $2.500 de interés por mora", anio: "Este año pagaste $2.500 en intereses por atraso." },
  inglés: { pago: "Paid on Oct 17, 7 days late · $2.500 in late-payment interest", anio: "This year you paid $2.500 in late-payment interest." },
};
for (const [idioma, consulta] of [["español", "idioma=es"], ["inglés", "idioma=en"]]) {
  for (const [modo, opciones] of [["escritorio", { viewport: { width: 1200, height: 820 } }], ["celular", { viewport: { width: 390, height: 844 }, colorScheme: "dark" }]]) {
    const t = TEXTOS_MO[idioma], donde = `(${idioma}, ${modo})`;
    const p = await navegador.newPage(opciones);
    p.on("pageerror", (e) => falla(`error de JavaScript en mora ${donde}: ${e.message}`));
    await p.goto(BASE + "?" + consulta);
    await p.waitForSelector(".app");
    const d = JSON.parse(fs.readFileSync(path.join(RAIZ, "ui", "demo.json"), "utf8"));
    d.config.bienvenida = true;
    d.movimientos.push({ id: "mora-pago", fecha: "2026-10-17", descripcion: "PLAN MOVIL EJEMPLO", monto: -15990, moneda: "CLP", cuenta: "banco-ejemplo", categoria: "cuentas" },
      { id: "mora-cargo", fecha: "2026-10-17", descripcion: "RECARGO POR ATRASO PLAN MOVIL", monto: -2500, moneda: "CLP", cuenta: "banco-ejemplo", categoria: "intereses" });
    await p.evaluate((x) => window.Alcancia.estado(x), d);
    const todo = async () => (await p.$eval(".contenido", (el) => el.textContent.replace(/\s+/g, " ")));
    if (!(await todo()).includes(t.anio)) falla(`el resumen dice lo pagado en intereses por atraso ${donde}`);
    await p.click('.nav [data-vista="compromisos"]');
    if (!(await todo()).includes(t.pago)) falla(`el compromiso dice el atraso y la mora ${donde}`);
    if (modo === "celular" && (await p.evaluate(() => document.documentElement.scrollWidth)) > 392) falla(`se sale de la pantalla con la mora ${donde}`);
    await p.close();
  }
}
console.log("  ✓ Mora: el pago atrasado dice los días y el interés, y el resumen lo pagado este año");

// Contraste (WCAG AA: 4.5) en modo claro y oscuro: la acción principal («+ Agregar», el único color de acción), el texto suave sobre
// el fondo y el rojo de lo atrasado sobre el panel.
for (const esquema of ["light", "dark"]) {
  const p = await navegador.newPage({ colorScheme: esquema });
  await p.goto(BASE); await p.waitForSelector(".nav-agregar");
  const c = await p.evaluate(() => {
    const lum = (s) => { const [r, g, b] = s.match(/[\d.]+/g).slice(0, 3).map((x) => { x = x / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    const ratio = (a, b) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05);
    const v = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
    const color = (x) => { const d = document.createElement("i"); d.style.color = x; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return c; };
    const cs = getComputedStyle(document.querySelector(".nav-agregar"));
    return { "botón principal": ratio(cs.color, cs.backgroundColor), "texto suave": ratio(color(v("--suave")), color(v("--fondo"))),
      "texto suave en tarjeta": ratio(color(v("--suave")), color(v("--panel"))), "rojo": ratio(color(v("--rojo")), color(v("--panel"))), "verde": ratio(color(v("--verde")), color(v("--panel"))) };
  });
  for (const [k, r] of Object.entries(c)) if (r < 4.5) falla(`contraste de ${k} en modo ${esquema}: ${r.toFixed(2)} (mínimo 4.5)`);
  console.log(`  ✓ Contraste en modo ${esquema === "light" ? "claro" : "oscuro"}: ${Object.entries(c).map(([k, r]) => `${k} ${r.toFixed(2)}`).join(", ")}`);
  await p.close();
}

// Navegación: cuatro secciones y una sola acción «+». En celular, barra inferior fija en la zona del pulgar con objetivos de 44 px
// o más; en escritorio, barra lateral con «+ Agregar» arriba. Escape cierra la hoja de agregar.
for (const [modo, opciones] of [["escritorio", { viewport: { width: 1280, height: 820 } }], ["celular", { viewport: { width: 390, height: 844 }, colorScheme: "dark" }]]) {
  const p = await navegador.newPage(opciones);
  p.on("pageerror", (e) => falla(`error de JavaScript en la navegación (${modo}): ${e.message}`));
  await p.goto(BASE + "?idioma=es"); await p.waitForSelector(".nav");
  const nav = await p.evaluate(() => ({
    secciones: [...document.querySelectorAll(".nav [data-vista]")].map((b) => b.dataset.vista),
    alturas: [...document.querySelectorAll(".nav button")].map((b) => Math.round(b.getBoundingClientRect().height)),
    anchos: [...document.querySelectorAll(".nav button")].map((b) => Math.round(b.getBoundingClientRect().width)),
    abajo: Math.round(document.querySelector(".lateral").getBoundingClientRect().bottom), alto: innerHeight,
    agregarArriba: document.querySelector(".nav-agregar").getBoundingClientRect().top < document.querySelector('.nav [data-vista="resumen"]').getBoundingClientRect().top,
  }));
  if (nav.secciones.join() !== "resumen,movimientos,compromisos,mas") falla(`la navegación tiene 4 secciones (${modo}): ${nav.secciones}`);
  if (nav.alturas.some((h) => h < 44) || nav.anchos.some((w) => w < 44)) falla(`los botones de la navegación miden 44 px o más (${modo}): ${nav.alturas} / ${nav.anchos}`);
  if (modo === "celular" && nav.abajo !== nav.alto) falla(`en celular la barra va fija abajo (${nav.abajo} de ${nav.alto})`);
  if (modo === "escritorio" && !nav.agregarArriba) falla("en escritorio «+ Agregar» va arriba de las secciones");
  for (const v of ["movimientos", "compromisos", "mas", "resumen"]) {
    await p.click(`.nav [data-vista="${v}"]`);
    if ((await p.$eval(".nav [aria-current]", (b) => b.dataset.vista)) !== v) falla(`la sección elegida queda marcada (${v}, ${modo})`);
  }
  await p.click('.nav [data-vista="mas"]'); await p.click('.lista-mas [data-vista="conexiones"]');
  if ((await p.$eval(".nav [aria-current]", (b) => b.dataset.vista)) !== "mas") falla(`Conexiones vive en «Más» (${modo})`);
  await p.click(".nav-agregar");
  if (!(await p.$(".dialogo #t-agregar"))) falla(`«+» abre la hoja de agregar (${modo})`);
  await p.keyboard.press("Escape");
  if (await p.$(".dialogo")) falla(`Escape cierra la hoja de agregar (${modo})`);
  await p.close();
}
console.log("  ✓ Navegación: 4 secciones, «+» único, barra inferior en celular y lateral en escritorio");

await navegador.close();
servidor.close();
if (errores.length) { console.log(`\n✗ ${errores.length} problemas`); process.exit(1); }
console.log("✓ Interfaz OK");
