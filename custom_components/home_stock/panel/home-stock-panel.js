function e(e,t,i,s){var r,n=arguments.length,a=n<3?t:null===s?s=Object.getOwnPropertyDescriptor(t,i):s;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)a=Reflect.decorate(e,t,i,s);else for(var o=e.length-1;o>=0;o--)(r=e[o])&&(a=(n<3?r(a):n>3?r(t,i,a):r(t,i))||a);return n>3&&a&&Object.defineProperty(t,i,a),a}"function"==typeof SuppressedError&&SuppressedError;
/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const t=globalThis,i=t.ShadowRoot&&(void 0===t.ShadyCSS||t.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,s=Symbol(),r=new WeakMap;let n=class{constructor(e,t,i){if(this._$cssResult$=!0,i!==s)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o;const t=this.t;if(i&&void 0===e){const i=void 0!==t&&1===t.length;i&&(e=r.get(t)),void 0===e&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&r.set(t,e))}return e}toString(){return this.cssText}};const a=(e,...t)=>{const i=1===e.length?e[0]:t.reduce((t,i,s)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if("number"==typeof e)return e;throw Error("Value passed to 'css' function must be a 'css' function result: "+e+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+e[s+1],e[0]);return new n(i,e,s)},o=i?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t="";for(const i of e.cssRules)t+=i.cssText;return(e=>new n("string"==typeof e?e:e+"",void 0,s))(t)})(e):e,{is:l,defineProperty:c,getOwnPropertyDescriptor:u,getOwnPropertyNames:h,getOwnPropertySymbols:p,getPrototypeOf:d}=Object,m=globalThis,g=m.trustedTypes,v=g?g.emptyScript:"",b=m.reactiveElementPolyfillSupport,f=(e,t)=>e,x={toAttribute(e,t){switch(t){case Boolean:e=e?v:null;break;case Object:case Array:e=null==e?e:JSON.stringify(e)}return e},fromAttribute(e,t){let i=e;switch(t){case Boolean:i=null!==e;break;case Number:i=null===e?null:Number(e);break;case Object:case Array:try{i=JSON.parse(e)}catch(e){i=null}}return i}},$=(e,t)=>!l(e,t),y={attribute:!0,type:String,converter:x,reflect:!1,useDefault:!1,hasChanged:$};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */Symbol.metadata??=Symbol("metadata"),m.litPropertyMetadata??=new WeakMap;let _=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=y){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){const i=Symbol(),s=this.getPropertyDescriptor(e,i,t);void 0!==s&&c(this.prototype,e,s)}}static getPropertyDescriptor(e,t,i){const{get:s,set:r}=u(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:s,set(t){const n=s?.call(this);r?.call(this,t),this.requestUpdate(e,n,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??y}static _$Ei(){if(this.hasOwnProperty(f("elementProperties")))return;const e=d(this);e.finalize(),void 0!==e.l&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(f("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(f("properties"))){const e=this.properties,t=[...h(e),...p(e)];for(const i of t)this.createProperty(i,e[i])}const e=this[Symbol.metadata];if(null!==e){const t=litPropertyMetadata.get(e);if(void 0!==t)for(const[e,i]of t)this.elementProperties.set(e,i)}this._$Eh=new Map;for(const[e,t]of this.elementProperties){const i=this._$Eu(e,t);void 0!==i&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){const t=[];if(Array.isArray(e)){const i=new Set(e.flat(1/0).reverse());for(const e of i)t.unshift(o(e))}else void 0!==e&&t.push(o(e));return t}static _$Eu(e,t){const i=t.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof e?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),void 0!==this.renderRoot&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){const e=new Map,t=this.constructor.elementProperties;for(const i of t.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){const e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((e,s)=>{if(i)e.adoptedStyleSheets=s.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(const i of s){const s=document.createElement("style"),r=t.litNonce;void 0!==r&&s.setAttribute("nonce",r),s.textContent=i.cssText,e.appendChild(s)}})(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,i){this._$AK(e,i)}_$ET(e,t){const i=this.constructor.elementProperties.get(e),s=this.constructor._$Eu(e,i);if(void 0!==s&&!0===i.reflect){const r=(void 0!==i.converter?.toAttribute?i.converter:x).toAttribute(t,i.type);this._$Em=e,null==r?this.removeAttribute(s):this.setAttribute(s,r),this._$Em=null}}_$AK(e,t){const i=this.constructor,s=i._$Eh.get(e);if(void 0!==s&&this._$Em!==s){const e=i.getPropertyOptions(s),r="function"==typeof e.converter?{fromAttribute:e.converter}:void 0!==e.converter?.fromAttribute?e.converter:x;this._$Em=s;const n=r.fromAttribute(t,e.type);this[s]=n??this._$Ej?.get(s)??n,this._$Em=null}}requestUpdate(e,t,i,s=!1,r){if(void 0!==e){const n=this.constructor;if(!1===s&&(r=this[e]),i??=n.getPropertyOptions(e),!((i.hasChanged??$)(r,t)||i.useDefault&&i.reflect&&r===this._$Ej?.get(e)&&!this.hasAttribute(n._$Eu(e,i))))return;this.C(e,t,i)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:i,reflect:s,wrapped:r},n){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,n??t??this[e]),!0!==r||void 0!==n)||(this._$AL.has(e)||(this.hasUpdated||i||(t=void 0),this._$AL.set(e,t)),!0===s&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}const e=this.scheduleUpdate();return null!=e&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}const e=this.constructor.elementProperties;if(e.size>0)for(const[t,i]of e){const{wrapped:e}=i,s=this[t];!0!==e||this._$AL.has(t)||void 0===s||this.C(t,void 0,i,s)}}let e=!1;const t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};_.elementStyles=[],_.shadowRootOptions={mode:"open"},_[f("elementProperties")]=new Map,_[f("finalized")]=new Map,b?.({ReactiveElement:_}),(m.reactiveElementVersions??=[]).push("2.1.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const k=globalThis,w=e=>e,C=k.trustedTypes,A=C?C.createPolicy("lit-html",{createHTML:e=>e}):void 0,E="$lit$",q=`lit$${Math.random().toFixed(9).slice(2)}$`,L="?"+q,S=`<${L}>`,P=document,z=()=>P.createComment(""),M=e=>null===e||"object"!=typeof e&&"function"!=typeof e,j=Array.isArray,R="[ \t\n\f\r]",F=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,V=/-->/g,O=/>/g,N=RegExp(`>|${R}(?:([^\\s"'>=/]+)(${R}*=${R}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),H=/'/g,T=/"/g,D=/^(?:script|style|textarea|title)$/i,I=(e=>(t,...i)=>({_$litType$:e,strings:t,values:i}))(1),U=Symbol.for("lit-noChange"),B=Symbol.for("lit-nothing"),J=new WeakMap,Q=P.createTreeWalker(P,129);function Z(e,t){if(!j(e)||!e.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==A?A.createHTML(t):t}const G=(e,t)=>{const i=e.length-1,s=[];let r,n=2===t?"<svg>":3===t?"<math>":"",a=F;for(let t=0;t<i;t++){const i=e[t];let o,l,c=-1,u=0;for(;u<i.length&&(a.lastIndex=u,l=a.exec(i),null!==l);)u=a.lastIndex,a===F?"!--"===l[1]?a=V:void 0!==l[1]?a=O:void 0!==l[2]?(D.test(l[2])&&(r=RegExp("</"+l[2],"g")),a=N):void 0!==l[3]&&(a=N):a===N?">"===l[0]?(a=r??F,c=-1):void 0===l[1]?c=-2:(c=a.lastIndex-l[2].length,o=l[1],a=void 0===l[3]?N:'"'===l[3]?T:H):a===T||a===H?a=N:a===V||a===O?a=F:(a=N,r=void 0);const h=a===N&&e[t+1].startsWith("/>")?" ":"";n+=a===F?i+S:c>=0?(s.push(o),i.slice(0,c)+E+i.slice(c)+q+h):i+q+(-2===c?t:h)}return[Z(e,n+(e[i]||"<?>")+(2===t?"</svg>":3===t?"</math>":"")),s]};class W{constructor({strings:e,_$litType$:t},i){let s;this.parts=[];let r=0,n=0;const a=e.length-1,o=this.parts,[l,c]=G(e,t);if(this.el=W.createElement(l,i),Q.currentNode=this.el.content,2===t||3===t){const e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;null!==(s=Q.nextNode())&&o.length<a;){if(1===s.nodeType){if(s.hasAttributes())for(const e of s.getAttributeNames())if(e.endsWith(E)){const t=c[n++],i=s.getAttribute(e).split(q),a=/([.?@])?(.*)/.exec(t);o.push({type:1,index:r,name:a[2],strings:i,ctor:"."===a[1]?te:"?"===a[1]?ie:"@"===a[1]?se:ee}),s.removeAttribute(e)}else e.startsWith(q)&&(o.push({type:6,index:r}),s.removeAttribute(e));if(D.test(s.tagName)){const e=s.textContent.split(q),t=e.length-1;if(t>0){s.textContent=C?C.emptyScript:"";for(let i=0;i<t;i++)s.append(e[i],z()),Q.nextNode(),o.push({type:2,index:++r});s.append(e[t],z())}}}else if(8===s.nodeType)if(s.data===L)o.push({type:2,index:r});else{let e=-1;for(;-1!==(e=s.data.indexOf(q,e+1));)o.push({type:7,index:r}),e+=q.length-1}r++}}static createElement(e,t){const i=P.createElement("template");return i.innerHTML=e,i}}function Y(e,t,i=e,s){if(t===U)return t;let r=void 0!==s?i._$Co?.[s]:i._$Cl;const n=M(t)?void 0:t._$litDirective$;return r?.constructor!==n&&(r?._$AO?.(!1),void 0===n?r=void 0:(r=new n(e),r._$AT(e,i,s)),void 0!==s?(i._$Co??=[])[s]=r:i._$Cl=r),void 0!==r&&(t=Y(e,r._$AS(e,t.values),r,s)),t}class K{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){const{el:{content:t},parts:i}=this._$AD,s=(e?.creationScope??P).importNode(t,!0);Q.currentNode=s;let r=Q.nextNode(),n=0,a=0,o=i[0];for(;void 0!==o;){if(n===o.index){let t;2===o.type?t=new X(r,r.nextSibling,this,e):1===o.type?t=new o.ctor(r,o.name,o.strings,this,e):6===o.type&&(t=new re(r,this,e)),this._$AV.push(t),o=i[++a]}n!==o?.index&&(r=Q.nextNode(),n++)}return Q.currentNode=P,s}p(e){let t=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(e,i,t),t+=i.strings.length-2):i._$AI(e[t])),t++}}class X{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,i,s){this.type=2,this._$AH=B,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=i,this.options=s,this._$Cv=s?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode;const t=this._$AM;return void 0!==t&&11===e?.nodeType&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=Y(this,e,t),M(e)?e===B||null==e||""===e?(this._$AH!==B&&this._$AR(),this._$AH=B):e!==this._$AH&&e!==U&&this._(e):void 0!==e._$litType$?this.$(e):void 0!==e.nodeType?this.T(e):(e=>j(e)||"function"==typeof e?.[Symbol.iterator])(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==B&&M(this._$AH)?this._$AA.nextSibling.data=e:this.T(P.createTextNode(e)),this._$AH=e}$(e){const{values:t,_$litType$:i}=e,s="number"==typeof i?this._$AC(e):(void 0===i.el&&(i.el=W.createElement(Z(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===s)this._$AH.p(t);else{const e=new K(s,this),i=e.u(this.options);e.p(t),this.T(i),this._$AH=e}}_$AC(e){let t=J.get(e.strings);return void 0===t&&J.set(e.strings,t=new W(e)),t}k(e){j(this._$AH)||(this._$AH=[],this._$AR());const t=this._$AH;let i,s=0;for(const r of e)s===t.length?t.push(i=new X(this.O(z()),this.O(z()),this,this.options)):i=t[s],i._$AI(r),s++;s<t.length&&(this._$AR(i&&i._$AB.nextSibling,s),t.length=s)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){const t=w(e).nextSibling;w(e).remove(),e=t}}setConnected(e){void 0===this._$AM&&(this._$Cv=e,this._$AP?.(e))}}class ee{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,i,s,r){this.type=1,this._$AH=B,this._$AN=void 0,this.element=e,this.name=t,this._$AM=s,this.options=r,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=B}_$AI(e,t=this,i,s){const r=this.strings;let n=!1;if(void 0===r)e=Y(this,e,t,0),n=!M(e)||e!==this._$AH&&e!==U,n&&(this._$AH=e);else{const s=e;let a,o;for(e=r[0],a=0;a<r.length-1;a++)o=Y(this,s[i+a],t,a),o===U&&(o=this._$AH[a]),n||=!M(o)||o!==this._$AH[a],o===B?e=B:e!==B&&(e+=(o??"")+r[a+1]),this._$AH[a]=o}n&&!s&&this.j(e)}j(e){e===B?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}}class te extends ee{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===B?void 0:e}}class ie extends ee{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==B)}}class se extends ee{constructor(e,t,i,s,r){super(e,t,i,s,r),this.type=5}_$AI(e,t=this){if((e=Y(this,e,t,0)??B)===U)return;const i=this._$AH,s=e===B&&i!==B||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,r=e!==B&&(i===B||s);s&&this.element.removeEventListener(this.name,this,i),r&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}}class re{constructor(e,t,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){Y(this,e)}}const ne=k.litHtmlPolyfillSupport;ne?.(W,X),(k.litHtmlVersions??=[]).push("3.3.3");const ae=globalThis;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */class oe extends _{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){const t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=((e,t,i)=>{const s=i?.renderBefore??t;let r=s._$litPart$;if(void 0===r){const e=i?.renderBefore??null;s._$litPart$=r=new X(t.insertBefore(z(),e),e,void 0,i??{})}return r._$AI(e),r})(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return U}}oe._$litElement$=!0,oe.finalized=!0,ae.litElementHydrateSupport?.({LitElement:oe});const le=ae.litElementPolyfillSupport;le?.({LitElement:oe}),(ae.litElementVersions??=[]).push("4.2.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const ce=e=>(t,i)=>{void 0!==i?i.addInitializer(()=>{customElements.define(e,t)}):customElements.define(e,t)},ue={attribute:!0,type:String,converter:x,reflect:!1,hasChanged:$},he=(e=ue,t,i)=>{const{kind:s,metadata:r}=i;let n=globalThis.litPropertyMetadata.get(r);if(void 0===n&&globalThis.litPropertyMetadata.set(r,n=new Map),"setter"===s&&((e=Object.create(e)).wrapped=!0),n.set(i.name,e),"accessor"===s){const{name:s}=i;return{set(i){const r=t.get.call(this);t.set.call(this,i),this.requestUpdate(s,r,e,!0,i)},init(t){return void 0!==t&&this.C(s,void 0,e,t),t}}}if("setter"===s){const{name:s}=i;return function(i){const r=this[s];t.call(this,i),this.requestUpdate(s,r,e,!0,i)}}throw Error("Unsupported decorator location: "+s)};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function pe(e){return(t,i)=>"object"==typeof i?he(e,t,i):((e,t,i)=>{const s=t.hasOwnProperty(i);return t.constructor.createProperty(i,e),s?Object.getOwnPropertyDescriptor(t,i):void 0})(e,t,i)}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function de(e){return pe({...e,state:!0,attribute:!1})}class me{constructor(e){this.hass=e}appeler(e,t={}){return this.hass.connection.sendMessagePromise({type:e,...t})}abonner(e){return this.hass.connection.subscribeMessage(e,{type:"home_stock/subscribe"})}appelerService(e,t,i={}){return this.hass.callService(e,t,i)}async televerserMedia(e,t){const i=new FormData;i.append("media_content_id",t),i.append("file",e);const s=this.hass.auth?.data?.access_token,r=await fetch("/api/media_source/local_source/upload",{method:"POST",body:i,headers:s?{authorization:`Bearer ${s}`}:{}});if(!r.ok)throw new Error(String(r.status));return(await r.json()).media_content_id}}function ge(e){return!!e&&"object"==typeof e&&"string"==typeof e.code&&"string"==typeof e.message}const ve=new Set(["not_loaded","invalid_field","invalid_value","not_found","already_exists","conversion_refused","shopping_refused","insufficient_stock"]);function be(e){return ve.has(e.code)?e.message:"Une action a été refusée et n’a pas pu être envoyée."}const fe="home_stock.file";class xe{constructor(e,t,i){this.stockage=e,this.envoyer=t,this.surRefus=i,this.actions=[],this.enVol=null;try{this.actions=JSON.parse(this.stockage.getItem(fe)??"[]")}catch{this.actions=[]}}ajouter(e,t){const i={...t};let s;"string"!=typeof i.idempotency_key&&(i.idempotency_key=crypto.randomUUID());const r=new Promise(e=>{s=e});let n;const a=new Promise(e=>{n=e});return this.actions.push({type:e,charge:i,resoudre:s,repondre:n}),this.ecrire(),{cle:i.idempotency_key,sort:r,reponse:a}}taille(){return this.actions.length}async rejouer(){const e=this.enVol,t=(async()=>{e&&await e.catch(()=>{}),await this.boucle()})();this.enVol=t;try{await t}finally{this.enVol===t&&(this.enVol=null)}}async boucle(){for(;this.actions.length;){const e=this.actions[0];let t;try{t=await this.envoyer(e.type,e.charge)}catch(t){if(ge(t)){this.actions.shift(),this.ecrire(),e.resoudre?.("refusee"),e.repondre?.(void 0),this.surRefus?.(e,be(t));continue}for(const e of this.actions)e.resoudre?.("en-attente"),e.repondre?.(void 0),e.resoudre=void 0,e.repondre=void 0;return}this.actions.shift(),this.ecrire(),e.resoudre?.("envoyee"),e.repondre?.(t)}}ecrire(){this.stockage.setItem(fe,JSON.stringify(this.actions.map(({type:e,charge:t})=>({type:e,charge:t}))))}}class $e{constructor(e){this.fenetre=e,this.voie="companion"}disponible(){return Boolean(this.fenetre?.externalApp?.externalBus||this.fenetre?.webkit?.messageHandlers?.externalBus)}lire(){return new Promise(e=>{const t=this.fenetre.externalBus;let i=!1;const s=s=>{i||(i=!0,clearTimeout(r),this.fenetre.externalBus=t,e(s))},r=setTimeout(()=>s(null),6e4);this.fenetre.externalBus=e=>{const t="string"==typeof e?JSON.parse(e):e;return"bar_code/scan_result"===t.command?(this.envoyer({type:"bar_code/close"}),s(String(t.payload.rawValue))):"bar_code/aborted"!==t.command&&"bar_code/close"!==t.command||s(null),!0},this.envoyer({type:"bar_code/scan",payload:{title:"Scanner un article",description:"Visez le code-barres",alternative_option_label:"Saisir le code"}})})}envoyer(e){const t=JSON.stringify(e);this.fenetre.externalApp?.externalBus?this.fenetre.externalApp.externalBus(t):this.fenetre.webkit.messageHandlers.externalBus.postMessage(e)}}const ye=["ean_13","ean_8","upc_a","upc_e","code_128"];class _e{constructor(e){this.fenetre=e,this.voie="navigateur"}disponible(){return Boolean(this.fenetre?.BarcodeDetector&&this.fenetre?.navigator?.mediaDevices)}async lire(){try{const e=new this.fenetre.BarcodeDetector({formats:ye});this.flux=await this.fenetre.navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}});const t=this.fenetre.document.createElement("video");t.srcObject=this.flux,t.setAttribute("playsinline","true"),t.setAttribute("muted","true"),t.style.cssText="position:fixed;inset:0;width:100%;height:100%;object-fit:cover;z-index:2147483647;background:#000;",this.fenetre.document.body.appendChild(t),this.video=t,await t.play();for(let i=0;i<300;i+=1){const i=await e.detect(t);if(i.length)return String(i[0].rawValue);await new Promise(e=>this.fenetre.requestAnimationFrame(e))}return null}finally{this.arreter()}}arreter(){this.flux?.getTracks().forEach(e=>e.stop()),this.flux=void 0,this.video?.remove(),this.video=void 0}}class ke{constructor(){this.voie="clavier"}disponible(){return!0}async lire(){return null}}const we=a`
  :host {
    --hs-space-1: 4px;
    --hs-space-2: 8px;
    --hs-space-3: 12px;
    --hs-space-4: 16px;
    --hs-space-5: 24px;
    --hs-space-6: 32px;

    --hs-radius-s: 8px;
    --hs-radius-m: 12px;
    --hs-radius-l: 16px;

    --hs-text: var(--primary-text-color, #141414);
    --hs-text-2: var(--secondary-text-color, #5e5e5e);
    --hs-surface: var(--card-background-color, #ffffff);
    --hs-surface-2: var(--secondary-background-color, #e5e5e5);
    --hs-divider: var(--divider-color, #0000001f);

    --hs-accent: var(--primary-color, #009ac7);
    --hs-danger: var(--error-color, #db4437);
    --hs-warning: var(--warning-color, #ffa600);

    /* Recalculés par on-color.ts au montage. Le sombre est le défaut le moins
       risqué sur une couleur de marque inconnue. Pas de --hs-on-danger : le
       danger ne se pose jamais en aplat sous du texte (spec § 6.1 ter,
       --error-color tombe pile à 4,29:1 des deux côtés), donc rien ne le lit. */
    --hs-on-accent: #141414;
    --hs-on-warning: #141414;

    --hs-font: var(--ha-font-family-body, Roboto, Noto, sans-serif);

    /* 62 px, pas 48 : la tablette cuisine (Fire 7) ouvre le même panneau, et
       c'est son seuil qui prime — il satisfait aussi le téléphone. */
    --hs-touch: 62px;

    font-family: var(--hs-font);
    color: var(--hs-text);
  }
`,Ce={label:"nom",brand:"marque",net_quantity:"poids net",image:"image",kcal_per_base_unit:"calories",proteins:"protéines",carbohydrates:"glucides",sugars:"sucres",added_sugars:"sucres ajoutés",fat:"matières grasses",saturated_fat:"graisses saturées",fiber:"fibres",salt:"sel",nutriscore:"Nutri-Score",nova:"classification NOVA",ecoscore:"Éco-score",allergens:"allergènes",traces:"traces",additives:"additifs",off_labels:"labels",off_raw:"réponse Open Food Facts"};function Ae(e,t,i){return null==e?"":"piece"===t?e.toFixed(2).replace(".",","):"g"===t||"ml"===t?null===i||i<=0?"":(e*i).toFixed(2).replace(".",","):""}function Ee(e,t,i){const s=Number.parseFloat(e.trim().replace(",","."));return Number.isFinite(s)?"piece"===t?s:"g"===t||"ml"===t?null===i||i<=0?null:s/i:null:null}function qe(e){return e.known?e.article?.net_quantity??null:e.off?.net_quantity??null}function Le(e){return e&&"object"==typeof e&&"message"in e&&"string"==typeof e.message?e.message:"Une erreur est survenue."}let Se=class extends oe{constructor(){super(...arguments),this.mode="rangement",this.productChoisi=null,this.nomNouveauProduit="",this.uniteNouveauProduit="piece",this.prixSaisi=null,this.poidsPaquet="",this.quantitePaquets=1,this.produitsBaseUnit={},this.rapportConversion=null,this.erreurConversion=null,this.erreurAction=null,this.erreurUnites=null,this.enCours=!1}willUpdate(e){if(e.has("resultat")&&this.resultat){this.productChoisi=this.resultat.preselected_product_id,this.nomNouveauProduit=this.resultat.off?.generic_name??"",this.uniteNouveauProduit=this.resultat.off?.net_unit??"piece";const e=qe(this.resultat);this.poidsPaquet=null!==e?String(e):"",this.prixSaisi=null,this.quantitePaquets=1,this.rapportConversion=null,this.erreurConversion=null,this.erreurAction=null,this.erreurUnites=null,this.produitsBaseUnit={}}}updated(e){e.has("resultat")&&this.resultat&&!this.resultat.known&&this.resultat.candidates.length&&this.connexion&&this.chargerUnitesProduits()}async chargerUnitesProduits(){this.erreurUnites=null;try{const e=await this.connexion.appeler("home_stock/products/list"),t={};for(const i of e.products)t[i.id]=i.base_unit;this.produitsBaseUnit=t}catch{this.erreurUnites="Impossible de récupérer les informations du produit. Vérifiez la connexion."}}uniteConnue(){return this.resultat.known?this.resultat.product?.base_unit??null:"new"===this.productChoisi?this.uniteNouveauProduit:"number"==typeof this.productChoisi?this.produitsBaseUnit[this.productChoisi]??null:null}get poidsEffectif(){return function(e){const t=Number.parseFloat(e.trim().replace(",","."));return Number.isFinite(t)&&t>0?t:null}(this.poidsPaquet)}get valeurPrix(){if(null!==this.prixSaisi)return this.prixSaisi;const e=this.uniteConnue(),t="piece"===e?null:this.poidsEffectif;return Ae(this.resultat.price?.price_per_base_unit,e,t)}get raisonBlocage(){if(!this.resultat)return null;if(!this.resultat.known){if(!this.connexion)return"Connexion indisponible.";if(null===this.productChoisi)return"Choisissez un produit.";if("new"===this.productChoisi&&!this.nomNouveauProduit.trim())return"Donnez un nom au nouveau produit."}const e=this.uniteConnue();return null===e?this.erreurUnites??"Chargement des informations du produit…":"g"!==e&&"ml"!==e||null!==this.poidsEffectif?null:"Indiquez le poids du paquet pour calculer le prix."}get peutValider(){return!this.enCours&&null===this.raisonBlocage}enregistrerPoidsCorrige(e,t){const i={article_id:e,fields:{net_quantity:t}};this.file?this.file.ajouter("home_stock/article/update",i):this.connexion&&this.connexion.appeler("home_stock/article/update",i).catch(()=>{})}async valider(){if(this.peutValider){this.enCours=!0,this.erreurAction=null;try{const e=this.uniteConnue(),t="piece"===e?null:this.poidsEffectif,i=null===qe(this.resultat);let s,r=[];if(this.resultat.known)s=this.resultat.article.id,null!==t&&i&&this.enregistrerPoidsCorrige(s,t);else{const e={code:this.resultat.code};this.resultat.off_raw&&(e.off=this.resultat.off_raw),this.resultat.off_source&&(e.off_source=this.resultat.off_source),"new"===this.productChoisi?e.new_product={name:this.nomNouveauProduit.trim(),base_unit:this.uniteNouveauProduit}:e.product_id=this.productChoisi,null!==t&&i&&(e.fields={net_quantity:t});const n=await this.connexion.appeler("home_stock/article/create",e);s=n.article_id,r=n.off_dropped_fields??[]}const n={articleId:s,quantite:"piece"===e?this.quantitePaquets:t*this.quantitePaquets,prixUnitaire:Ee(this.valeurPrix,e,t),mode:this.mode,offDroppedFields:r};this.dispatchEvent(new CustomEvent("article-pret",{detail:n,bubbles:!0,composed:!0}))}catch(e){this.erreurAction=Le(e)}finally{this.enCours=!1}}}mangerProduit(e){this.dispatchEvent(new CustomEvent("manger-produit",{detail:{product_id:e},bubbles:!0,composed:!0}))}async voirEffetConversion(){const e=this.resultat.conversion_offer;if(e&&this.connexion){this.erreurConversion=null;try{this.rapportConversion=await this.connexion.appeler("home_stock/product/convert_unit",{product_id:e.product_id,to_unit:e.to_unit,reference_quantity:e.reference_quantity,dry_run:!0})}catch(e){this.erreurConversion=Le(e)}}}async appliquerConversion(){const e=this.resultat.conversion_offer;if(e&&this.connexion&&this.rapportConversion){this.erreurConversion=null;try{this.rapportConversion=await this.connexion.appeler("home_stock/product/convert_unit",{product_id:e.product_id,to_unit:e.to_unit,reference_quantity:e.reference_quantity,dry_run:!1})}catch(e){this.erreurConversion=Le(e)}}}rendreRattachement(){return this.resultat.known?B:I`
      <section class="rattachement">
        ${this.resultat.candidates.map(e=>I`
          <label class="candidat">
            <input type="radio" name="produit" .value=${String(e.product_id)}
              .checked=${this.productChoisi===e.product_id}
              @change=${()=>{this.productChoisi=e.product_id}} />
            <span>${e.name}</span>
          </label>
        `)}
        <label class="candidat nouveau">
          <input type="radio" name="produit" value="new"
            .checked=${"new"===this.productChoisi}
            @change=${()=>{this.productChoisi="new"}} />
          <span>Nouveau produit</span>
        </label>
        ${"new"===this.productChoisi?I`
          <div class="nouveau-produit">
            <input class="nom-nouveau" placeholder="Nom du produit" .value=${this.nomNouveauProduit}
              @input=${e=>{this.nomNouveauProduit=e.target.value}} />
            <select class="unite-nouveau" .value=${this.uniteNouveauProduit}
              @change=${e=>{this.uniteNouveauProduit=e.target.value}}>
              <option value="g">grammes</option>
              <option value="ml">millilitres</option>
              <option value="piece">à la pièce</option>
            </select>
          </div>`:B}
        ${this.erreurUnites?I`
          <p class="erreur-unite">${this.erreurUnites}</p>
          <button class="reessayer-unite" @click=${()=>{this.chargerUnitesProduits()}}>
            Réessayer
          </button>`:B}
      </section>
    `}rendreAlerteOff(){const e=this.resultat;return e.known||e.off?B:e.throttled?I`<p class="alerte-off">Open Food Facts limite les requêtes en ce moment — réessayez
        dans un instant plutôt que de créer un doublon.</p>`:e.timed_out?I`<p class="alerte-off">Open Food Facts n'a pas répondu à temps — le produit existe
        peut-être déjà là-bas, réessayez avant de créer un doublon.</p>`:B}rendreConversion(){const e=this.resultat.conversion_offer;return e?I`
      <section class="conversion-offre">
        <p>Passer de pièce à ${e.to_unit} — 1 unité = ${e.reference_quantity} ${e.to_unit}</p>
        ${this.rapportConversion?I`
          <p class="rapport-conversion">
            ${this.rapportConversion.articles} article(s), ${this.rapportConversion.batches} lot(s),
            ${this.rapportConversion.movements} mouvement(s) concernés
            ${this.rapportConversion.articles_using_reference.length?I`
              — dont ${this.rapportConversion.articles_using_reference.length} article(s) qui seront
              re-pesé(s) avec un poids de référence estimé, faute de poids propre.`:"."}
          </p>
          ${this.rapportConversion.applied?I`<p class="conversion-appliquee">Conversion appliquée.</p>`:I`<button class="appliquer-conversion" @click=${this.appliquerConversion}>
                Appliquer la conversion
              </button>`}
        `:I`<button class="voir-effet" @click=${this.voirEffetConversion}>
            Voir l'effet du changement d'unité
          </button>`}
        ${this.erreurConversion?I`<p class="erreur-conversion">${this.erreurConversion}</p>`:B}
      </section>
    `:B}render(){if(!this.resultat)return B;const e=this.resultat,t=e.off?.label??e.article?.label??e.product?.name??"Article",i=e.off?.brand??e.article?.brand??null,s=e.article?.net_quantity??e.off?.net_quantity??null,r=e.product?.base_unit??e.off?.net_unit??"",n=e.off?.image??e.article?.image??null,a=e.off?.nutriscore??e.article?.nutriscore??null,o=function(e){const t=e.off?.nutrition_per_100?.kcal;if(null!=t)return t;const i=e.article?.kcal_per_base_unit,s=e.product?.base_unit;return null==i||"g"!==s&&"ml"!==s?null:100*i}(e),l=this.uniteConnue(),c="piece"===l?null:this.poidsEffectif,u="g"===l||"ml"===l?Ee(this.valeurPrix,l,c):null,h=null!=u?1e3*u:null,p="ml"===l?"L":"kg";return I`
      <section class="entete">
        ${n?I`<img class="image" src=${n} alt="" />`:B}
        <h2 class="nom">${t}</h2>
        ${i?I`<p class="marque">${i}</p>`:B}
        ${s?I`<p class="poids">${s} ${r}</p>`:B}
        ${a?I`<p class="nutriscore">Nutri-Score ${a.toUpperCase()}</p>`:B}
        ${null!=o?I`<p class="kcal">${Math.round(o)} kcal / 100 g</p>`:B}
      </section>

      ${this.rendreAlerteOff()}
      ${this.rendreRattachement()}

      <section class="prix">
        <p class="prix-provenance">${d=e.price,d&&null!=d.price_per_base_unit&&d.source?"store"===d.source?d.store?`dernier prix ${d.store}`:"dernier prix en magasin":"open_prices"===d.source?"Open Prices":"dernier prix connu":"Aucun prix connu"}</p>
        ${"g"!==l&&"ml"!==l||null!==qe(e)?B:I`
          <label class="poids-label">
            Poids du paquet
            <input class="poids-champ" inputmode="decimal" placeholder="ex. 500" .value=${this.poidsPaquet}
              @input=${e=>{this.poidsPaquet=e.target.value}} />
            <span>${"ml"===l?"ml":"g"}</span>
          </label>`}
        <label class="prix-label">
          ${"piece"===l?"Prix payé (€ / unité)":"Prix payé (paquet)"}
          <input class="prix-champ" inputmode="decimal" .value=${this.valeurPrix}
            @input=${e=>{this.prixSaisi=e.target.value}} />
        </label>
        ${null!=h?I`
          <p class="prix-detail">soit ${h.toFixed(2).replace(".",",")} €/${p}</p>
        `:B}
      </section>

      <section class="quantite">
        <span>Quantité</span>
        <button class="moins" aria-label="Retirer un" ?disabled=${this.quantitePaquets<=1}
          @click=${()=>{this.quantitePaquets=Math.max(1,this.quantitePaquets-1)}}>−</button>
        <span class="valeur-quantite">${this.quantitePaquets}</span>
        <button class="plus" aria-label="Ajouter un"
          @click=${()=>{this.quantitePaquets+=1}}>+</button>
      </section>

      ${this.rendreConversion()}

      ${this.raisonBlocage?I`<p class="motif-blocage">${this.raisonBlocage}</p>`:B}
      ${this.erreurAction?I`<p class="erreur-action">${this.erreurAction}</p>`:B}

      <button class="action-principale" ?disabled=${!this.peutValider} @click=${this.valider}>
        ${"panier"===this.mode?"Au panier":"Ranger"}
      </button>
      ${null!=e.product?.id?I`
        <button type="button" class="manger" @click=${()=>this.mangerProduit(e.product.id)}>
          Manger
        </button>
      `:B}
    `;var d}};Se.styles=[we,a`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--hs-text); }
    .image { max-width: 100%; max-height: 160px; display: block; margin: 0 auto 8px; border-radius: 8px; }
    .nom { margin: 0; font-size: 1.2rem; }
    .marque, .poids, .nutriscore, .kcal { margin: 2px 0; color: var(--hs-text-2); }
    /* --hs-on-warning est recalculé au montage : l'aplat reste lisible sur
       les trois palettes mesurées. */
    .alerte-off {
      background: var(--hs-warning); color: var(--hs-on-warning);
      padding: 8px; border-radius: 8px; margin: 8px 0;
    }
    .candidat { display: flex; align-items: center; gap: 8px; min-height: var(--hs-touch); }
    .candidat input { width: 22px; height: 22px; }
    .nom-nouveau, .prix-champ, .poids-champ, .unite-nouveau {
      min-height: var(--hs-touch); font-size: 1rem; padding: 4px 8px; box-sizing: border-box; width: 100%;
    }
    .prix { margin: 12px 0; }
    .prix-provenance { color: var(--hs-text-2); margin: 0 0 4px; }
    .prix-detail { color: var(--hs-text-2); font-size: 0.85rem; }
    .poids-label, .prix-label { display: block; margin: 8px 0; }
    .quantite { display: flex; align-items: center; gap: 12px; margin: 12px 0; }
    .quantite button {
      min-width: var(--hs-touch); min-height: var(--hs-touch); font-size: 1.5rem; border-radius: 8px; border: none;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .valeur-quantite { min-width: 32px; text-align: center; font-size: 1.2rem; }
    .conversion-offre { margin: 12px 0; padding: 8px; border-radius: 8px; background: var(--hs-surface-2); }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .motif-blocage, .erreur-action, .erreur-conversion, .erreur-unite {
      color: var(--hs-text); border-left: 3px solid var(--hs-danger); padding-left: 8px; font-size: 0.9rem;
    }
    .reessayer-unite {
      min-height: var(--hs-touch); width: 100%; margin-top: 4px; border-radius: 8px; border: none;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .action-principale {
      display: block; width: 100%; min-height: var(--hs-touch); font-size: 1.2rem; border-radius: 12px;
      border: none; background: var(--hs-accent); color: var(--hs-on-accent);
      margin-top: 12px;
    }
    .action-principale:disabled { opacity: 0.5; }
    .manger {
      display: block; width: 100%; min-height: var(--hs-touch); font-size: 1rem; border-radius: 8px;
      border: none; background: var(--hs-surface-2); color: var(--hs-text);
      margin-top: 8px;
    }
    button.voir-effet, button.appliquer-conversion {
      min-height: var(--hs-touch); width: 100%; border-radius: 8px; border: none;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
  `],e([pe({attribute:!1})],Se.prototype,"resultat",void 0),e([pe({attribute:!1})],Se.prototype,"mode",void 0),e([pe({attribute:!1})],Se.prototype,"connexion",void 0),e([pe({attribute:!1})],Se.prototype,"file",void 0),e([de()],Se.prototype,"productChoisi",void 0),e([de()],Se.prototype,"nomNouveauProduit",void 0),e([de()],Se.prototype,"uniteNouveauProduit",void 0),e([de()],Se.prototype,"prixSaisi",void 0),e([de()],Se.prototype,"poidsPaquet",void 0),e([de()],Se.prototype,"quantitePaquets",void 0),e([de()],Se.prototype,"produitsBaseUnit",void 0),e([de()],Se.prototype,"rapportConversion",void 0),e([de()],Se.prototype,"erreurConversion",void 0),e([de()],Se.prototype,"erreurAction",void 0),e([de()],Se.prototype,"erreurUnites",void 0),e([de()],Se.prototype,"enCours",void 0),Se=e([ce("home-stock-fiche")],Se);let Pe=class extends oe{constructor(){super(...arguments),this.fenetre=window,this.derniereFiche=null,this.session=null,this.enAttente=0,this.saisieOuverte=!1,this.codeSaisi="",this.enCours=!1,this.erreur=null}obtenirScanner(){return this.scanner||(this.scanner=function(e){const t=new $e(e);if(t.disponible())return t;const i=new _e(e);return i.disponible()?i:new ke}(this.fenetre??window)),this.scanner}async lancerScan(){const e=this.obtenirScanner();if("clavier"!==e.voie){this.enCours=!0,this.erreur=null;try{const t=await e.lire();t&&this.emettreCode(t)}catch{this.erreur="La caméra n’a pas pu être utilisée. Essayez la saisie manuelle."}finally{this.enCours=!1}}else this.saisieOuverte=!0}emettreCode(e){this.saisieOuverte=!1,this.codeSaisi="",this.dispatchEvent(new CustomEvent("code-lu",{detail:{code:e},bubbles:!0,composed:!0}))}validerSaisie(){const e=this.codeSaisi.trim();e&&this.emettreCode(e)}render(){return I`
      ${this.session?I`
        <p class="session-banniere">
          Session ouverte${this.session.store?` — ${this.session.store}`:""}
        </p>`:B}

      <button class="bouton-scan" ?disabled=${this.enCours} @click=${this.lancerScan}>
        ${this.enCours?"Scan en cours…":"Scanner un article"}
      </button>

      ${this.erreur?I`<p class="erreur">${this.erreur}</p>`:B}

      ${this.derniereFiche?I`
        <section class="derniere-fiche">
          ${this.derniereFiche.image?I`<img src=${this.derniereFiche.image} alt="" />`:B}
          <p class="derniere-fiche-nom">
            ${this.derniereFiche.nom}${this.derniereFiche.marque?` — ${this.derniereFiche.marque}`:""}
          </p>
          <p class="derniere-fiche-statut">${this.derniereFiche.statut}</p>
          ${void 0!==this.derniereFiche.quantite?I`
            <p class="derniere-fiche-quantite">
              Quantité : ${this.derniereFiche.quantite}${null!=this.derniereFiche.prixTotal?` — ${this.derniereFiche.prixTotal.toFixed(2).replace(".",",")} €`:""}
            </p>`:B}
          ${this.derniereFiche.ignores?.length?I`
            <p class="derniere-fiche-ignores">
              Ignoré par Open Food Facts : ${e=this.derniereFiche.ignores,e.map(e=>Ce[e]??e).join(", ")}
            </p>`:B}
        </section>`:B}

      ${this.enAttente>0?I`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:B}

      <button class="bouton-saisie" @click=${()=>{this.saisieOuverte=!this.saisieOuverte}}>
        Saisir le code
      </button>

      ${this.saisieOuverte?I`
        <div class="saisie-manuelle">
          <input class="champ-code" inputmode="numeric" placeholder="Code-barres" .value=${this.codeSaisi}
            @input=${e=>{this.codeSaisi=e.target.value}}
            @keydown=${e=>{"Enter"===e.key&&this.validerSaisie()}} />
          <button class="valider-saisie" @click=${this.validerSaisie}>Valider</button>
        </div>`:B}
    `;var e}};function ze(e){return`${e.toFixed(2).replace(".",",")} €`}Pe.styles=[we,a`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--hs-text); }
    .session-banniere {
      background: var(--hs-surface-2); padding: 8px 12px; border-radius: 8px;
      margin: 0 0 12px; text-align: center;
    }
    .bouton-scan {
      display: block; width: 100%; min-height: 96px; font-size: 1.4rem; font-weight: 600;
      border-radius: 16px; border: none; background: var(--hs-accent);
      color: var(--hs-on-accent);
    }
    .bouton-scan:disabled { opacity: 0.6; }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .erreur { color: var(--hs-text); border-left: 3px solid var(--hs-danger); padding-left: 8px; }
    .derniere-fiche {
      margin: 16px 0; padding: 8px; border-radius: 8px; background: var(--hs-surface-2);
      display: flex; flex-direction: column; align-items: center; gap: 4px;
    }
    .derniere-fiche img { max-height: 72px; max-width: 100%; border-radius: 6px; }
    .derniere-fiche-ignores, .derniere-fiche-quantite {
      color: var(--hs-text-2); font-size: 0.85rem; text-align: center;
    }
    .en-attente {
      text-align: center; color: var(--hs-text-2); font-size: 0.85rem; margin: 8px 0 0;
    }
    .bouton-saisie {
      display: block; width: 100%; min-height: var(--hs-touch); margin-top: 16px; border-radius: 8px;
      border: 1px solid var(--hs-divider); background: transparent; color: var(--hs-text);
    }
    .saisie-manuelle { display: flex; gap: 8px; margin-top: 8px; }
    .champ-code { flex: 1; min-height: var(--hs-touch); font-size: 1rem; padding: 4px 8px; box-sizing: border-box; }
    .valider-saisie {
      min-height: var(--hs-touch); min-width: var(--hs-touch); border-radius: 8px; border: none;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
  `],e([pe({attribute:!1})],Pe.prototype,"fenetre",void 0),e([pe({attribute:!1})],Pe.prototype,"derniereFiche",void 0),e([pe({attribute:!1})],Pe.prototype,"session",void 0),e([pe({attribute:!1})],Pe.prototype,"enAttente",void 0),e([de()],Pe.prototype,"saisieOuverte",void 0),e([de()],Pe.prototype,"codeSaisi",void 0),e([de()],Pe.prototype,"enCours",void 0),e([de()],Pe.prototype,"erreur",void 0),Pe=e([ce("home-stock-scanner")],Pe);let Me=class extends oe{constructor(){super(...arguments),this.donnees=null,this.enAttente=0,this.ligneArmee=null,this.prixSaisiParLigne={},this.erreurPrixParLigne={},this.deltaParLigne={},this.quantiteVueParLigne={},this.seulementHorsListe=!1}willUpdate(e){if(e.has("donnees")){this.ligneArmee=null;for(const e of this.donnees?.lines??[])if(this.quantiteVueParLigne[e.id]!==e.quantity&&(this.quantiteVueParLigne[e.id]=e.quantity,this.deltaParLigne[e.id])){const{[e.id]:t,...i}=this.deltaParLigne;this.deltaParLigne=i}}}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()),i.sort.then(e=>"envoyee"===e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}quantiteAffichee(e){return e.quantity+(this.deltaParLigne[e.id]??0)}ajusterQuantite(e,t){this.ligneArmee=null;const i=(this.deltaParLigne[e.id]??0)+t,s=e.quantity+i;s<=0||(this.deltaParLigne={...this.deltaParLigne,[e.id]:i},this.ecrire("home_stock/session/update_line",{line_id:e.id,quantity:s}))}saisirPrix(e,t){this.ligneArmee=null,this.prixSaisiParLigne={...this.prixSaisiParLigne,[e.id]:t}}validerPrix(e){this.ligneArmee=null;const t=this.prixSaisiParLigne[e.id];if(void 0===t)return;const i=Ee(t,e.base_unit,e.net_quantity);if(null===i)return void(this.erreurPrixParLigne={...this.erreurPrixParLigne,[e.id]:"Prix non enregistré : poids du paquet inconnu."});if(this.erreurPrixParLigne[e.id]){const{[e.id]:t,...i}=this.erreurPrixParLigne;this.erreurPrixParLigne=i}this.ecrire("home_stock/session/update_line",{line_id:e.id,unit_price:i});const{[e.id]:s,...r}=this.prixSaisiParLigne;this.prixSaisiParLigne=r}supprimer(e){this.ecrire("home_stock/session/remove_line",{line_id:e.id}),this.ligneArmee=null}passerEnCaisse(){this.ligneArmee=null,this.ecrire("home_stock/session/checkout",{})}valeurPrix(e){const t=this.prixSaisiParLigne[e.id];return void 0!==t?t:Ae(e.unit_price,e.base_unit,e.net_quantity)}rendreLigne(e){const t=function(e){return"piece"===e.base_unit?1:e.net_quantity&&e.net_quantity>0?e.net_quantity:1}(e),i=this.quantiteAffichee(e),s=e.article_label??e.product_name;return I`
      <article class="ligne">
        ${e.image?I`<img class="image" src=${e.image} alt="" />`:B}
        <div class="infos">
          <p class="nom">${s}${e.brand?` — ${e.brand}`:""}</p>
          <div class="quantite">
            <button class="moins" aria-label="Retirer un paquet" ?disabled=${i<=t}
              @click=${()=>this.ajusterQuantite(e,-t)}>−</button>
            <span class="valeur-quantite">
              ${i}${"piece"!==e.base_unit?` ${e.base_unit}`:""}
            </span>
            <button class="plus" aria-label="Ajouter un paquet"
              @click=${()=>this.ajusterQuantite(e,t)}>+</button>
          </div>
          <label class="prix-label">
            Prix
            <input class="prix-champ" inputmode="decimal" .value=${this.valeurPrix(e)}
              @input=${t=>this.saisirPrix(e,t.target.value)}
              @change=${()=>this.validerPrix(e)} />
          </label>
          ${this.erreurPrixParLigne[e.id]?I`
            <p class="erreur-prix">${this.erreurPrixParLigne[e.id]}</p>
          `:B}
        </div>
        ${this.ligneArmee===e.id?I`
          <div class="confirmation-suppression">
            <button class="confirmer-suppression" @click=${()=>this.supprimer(e)}>Confirmer</button>
            <button class="annuler-suppression" @click=${()=>{this.ligneArmee=null}}>Annuler</button>
          </div>
        `:I`
          <button class="supprimer" aria-label="Retirer du panier" @click=${()=>{this.ligneArmee=e.id}}>
            ×
          </button>
        `}
      </article>
    `}rendreRepartition(e){if(void 0===e.estimated)return B;const t=e.unpriced_lines??0,i=(e.list_items??0)>0?`${e.checked_items??0} / ${e.list_items} de la liste`:null;return I`
      <p class="repartition">${`dont ${ze(e.estimated)} estimé`+(t>0?`, ${t} ligne${t>1?"s":""} sans prix`:"")}</p>
      ${i?I`<p class="progression">${i}</p>`:B}
    `}render(){const e=this.donnees;if(!e)return I`<p class="vide">Aucune session de courses ouverte.</p>`;const t=function(e){const t=[];for(const i of e){const e=i.aisle_name??"Sans rayon",s=t[t.length-1];s&&s.rayon===e?s.lignes.push(i):t.push({rayon:e,lignes:[i]})}return t}(e.lines),i="shopping"!==e.session.state;return I`
      <section class="entete">
        <p class="magasin">${e.session.store??"Sans enseigne"}</p>
        <p class="total">${ze(e.totals.total)}</p>
      </section>

      ${this.rendreRepartition(e.totals)}

      ${this.enAttente>0?I`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:B}

      ${0===e.lines.length?I`<p class="vide">Le panier est vide.</p>`:B}

      ${(e.totals.off_list_lines??0)>0?I`
        <button class="hors-liste"
          aria-pressed=${this.seulementHorsListe?"true":"false"}
          @click=${()=>{this.seulementHorsListe=!this.seulementHorsListe}}>
          ${`${e.totals.off_list_lines} hors liste`}
        </button>
      `:B}

      ${t.map(e=>I`
        <section class="rayon">
          <h3 class="rayon-nom">${e.rayon}</h3>
          ${e.lignes.map(e=>this.rendreLigne(e))}
        </section>
      `)}

      <button class="checkout" ?disabled=${0===e.totals.lines||i} @click=${this.passerEnCaisse}>
        ${i?"Déjà en caisse":"Passage en caisse"}
      </button>
    `}};Me.styles=[we,a`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--hs-text); }
    .entete { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
    .magasin { font-weight: 600; margin: 0; }
    .total { font-size: 1.3rem; font-weight: 700; margin: 0; }
    .repartition, .progression { margin: 0 0 4px; font-size: 0.85rem; color: var(--hs-text-2); }
    .hors-liste {
      min-height: var(--hs-touch); width: 100%; border-radius: 8px; border: none; font-size: 0.9rem;
      background: var(--hs-surface-2); color: var(--hs-text);
      margin-bottom: 8px;
    }
    .hors-liste[aria-pressed='true'] { background: var(--hs-accent); color: var(--hs-on-accent); }
    .en-attente { text-align: center; color: var(--hs-text-2); font-size: 0.85rem; margin: 4px 0 8px; }
    .vide { color: var(--hs-text-2); text-align: center; }
    .rayon-nom {
      margin: 16px 0 4px; font-size: 0.9rem; text-transform: uppercase;
      color: var(--hs-text-2); letter-spacing: 0.04em;
    }
    .ligne {
      display: flex; align-items: center; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--hs-divider);
    }
    .image { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; flex-shrink: 0; }
    .infos { flex: 1; min-width: 0; }
    .nom { margin: 0 0 4px; }
    .quantite { display: flex; align-items: center; gap: 8px; }
    .quantite button {
      min-width: var(--hs-touch); min-height: var(--hs-touch); font-size: 1.3rem; border-radius: 8px; border: none;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .quantite button:disabled { opacity: 0.5; }
    .valeur-quantite { min-width: 56px; text-align: center; }
    .prix-label { display: block; font-size: 0.85rem; margin-top: 4px; }
    .prix-champ { min-height: var(--hs-touch); width: 100%; box-sizing: border-box; font-size: 1rem; padding: 4px 8px; }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .erreur-prix {
      color: var(--hs-text); border-left: 3px solid var(--hs-danger);
      padding-left: 8px; font-size: 0.8rem; margin: 4px 0 0;
    }
    .supprimer {
      min-width: var(--hs-touch); min-height: var(--hs-touch); border-radius: 8px; border: 2px solid var(--hs-danger);
      background: var(--hs-surface); color: var(--hs-text); font-size: 1.2rem; flex-shrink: 0;
    }
    .confirmation-suppression { display: flex; flex-direction: column; gap: 4px; flex-shrink: 0; }
    .confirmer-suppression, .annuler-suppression {
      min-height: var(--hs-touch); min-width: var(--hs-touch); border-radius: 8px; border: none; font-size: 0.9rem;
    }
    .confirmer-suppression {
      background: var(--hs-surface); color: var(--hs-text); border: 2px solid var(--hs-danger);
    }
    .annuler-suppression { background: var(--hs-surface-2); color: var(--hs-text); }
    .checkout {
      display: block; width: 100%; min-height: var(--hs-touch); font-size: 1.2rem; border-radius: 12px; border: none;
      background: var(--hs-accent); color: var(--hs-on-accent); margin-top: 16px;
    }
    .checkout:disabled { opacity: 0.5; }
  `],e([pe({attribute:!1})],Me.prototype,"donnees",void 0),e([pe({attribute:!1})],Me.prototype,"connexion",void 0),e([pe({attribute:!1})],Me.prototype,"file",void 0),e([pe({attribute:!1})],Me.prototype,"enAttente",void 0),e([de()],Me.prototype,"ligneArmee",void 0),e([de()],Me.prototype,"prixSaisiParLigne",void 0),e([de()],Me.prototype,"erreurPrixParLigne",void 0),e([de()],Me.prototype,"deltaParLigne",void 0),e([de()],Me.prototype,"seulementHorsListe",void 0),Me=e([ce("home-stock-panier")],Me);let je=class extends oe{constructor(){super(...arguments),this.donnees=null,this.enAttente=0,this.magasins=[],this.magasinChoisi=null,this.magasinSaisi="",this.erreurMagasins=null,this.clotureArmee=!1,this.enCours=!1,this.message=null}connectedCallback(){super.connectedCallback(),this.chargerMagasins()}willUpdate(e){e.has("donnees")&&(this.clotureArmee=!1)}async chargerMagasins(){if(this.erreurMagasins=null,this.donnees?.stores?.length&&(this.magasins=this.donnees.stores),this.connexion)try{const e=await this.connexion.appeler("home_stock/stores/list");this.magasins=e.stores}catch{this.erreurMagasins="Impossible de récupérer les magasins connus. Saisissez-en un."}}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()),i.sort.then(e=>"envoyee"===e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}get chargeMagasin(){const e=this.magasinSaisi.trim();return e?{store:e}:this.magasinChoisi?{store_id:this.magasinChoisi.id}:{}}get magasinRetenu(){const e=this.magasinSaisi.trim();return e||(this.magasinChoisi?.name??null)}async ouvrir(){if(this.enCours)return;this.enCours=!0,this.message=null;const e=await this.ecrire("home_stock/session/start",this.chargeMagasin);this.enCours=!1,e?this.dispatchEvent(new CustomEvent("session-changee",{detail:{action:"ouverte"},bubbles:!0,composed:!0})):this.message="Envoi en attente de réseau : la session s’ouvrira à la reconnexion."}async clore(){if(!this.clotureArmee||this.enCours)return;this.enCours=!0,this.message=null;const e=await this.ecrire("home_stock/session/close",{});this.enCours=!1,this.clotureArmee=!1,e?this.dispatchEvent(new CustomEvent("session-changee",{detail:{action:"fermee"},bubbles:!0,composed:!0})):this.message="Envoi en attente de réseau : la session se clora à la reconnexion."}rendreOuverture(){return I`
      <h2 class="titre">Nouvelle session de courses</h2>
      <p class="explication">
        Choisissez le magasin : les scans partiront au panier au lieu d’aller directement au rangement.
      </p>

      ${this.magasins.length?I`
        <div class="pastilles">
          ${this.magasins.map(e=>I`
            <button class="pastille ${this.magasinChoisi?.id===e.id?"choisie":""}"
              aria-pressed=${this.magasinChoisi?.id===e.id?"true":"false"}
              @click=${()=>{this.magasinChoisi=e,this.magasinSaisi=""}}>
              ${e.name}
            </button>
          `)}
        </div>`:B}

      ${this.erreurMagasins?I`<p class="erreur">${this.erreurMagasins}</p>`:B}

      <label class="magasin-label">
        Autre magasin
        <input class="champ-magasin" placeholder="ex. Leclerc" .value=${this.magasinSaisi}
          @input=${e=>{this.magasinSaisi=e.target.value,this.magasinChoisi=null}} />
      </label>

      <p class="magasin-retenu">
        ${this.magasinRetenu?`Magasin : ${this.magasinRetenu}`:"Aucun magasin choisi — la session sera sans enseigne."}
      </p>

      <button class="ouvrir-session" ?disabled=${this.enCours} @click=${this.ouvrir}>
        ${this.enCours?"Ouverture…":"Ouvrir la session"}
      </button>
    `}rendreCloture(e){const t="shopping"===e.session.state,i=e.totals.pending;return I`
      <h2 class="titre">${t?"Session en cours":"Courses à ranger"}</h2>
      <p class="magasin-retenu">${e.session.store??"Sans enseigne"}</p>
      <p class="resume">
        ${e.totals.lines} ligne${e.totals.lines>1?"s":""} —
        ${s=e.totals.total,`${s.toFixed(2).replace(".",",")} €`}
      </p>
      ${t&&(e.totals.list_items??0)>0?I`
        <button class="emporter-liste" @click=${()=>this.dispatchEvent(new CustomEvent("aller-liste",{bubbles:!0,composed:!0}))}>
          ${`Emporter la liste (${e.totals.list_items})`}
        </button>
      `:B}

      ${t?B:I`
        <button class="photographier" @click=${()=>this.dispatchEvent(new CustomEvent("ticket-ouvert",{detail:{ticket:null,agent_configure:!0},bubbles:!0,composed:!0}))}>
          Photographier le ticket
        </button>
      `}

      ${i>0?I`
        <p class="restantes">
          ${i} ligne${i>1?"s":""} pas encore rangée${i>1?"s":""}.
          Clore la session les abandonne : rien n’entrera en stock pour elles.
        </p>`:B}

      ${this.clotureArmee?I`
        <div class="confirmation-cloture">
          <button class="confirmer-cloture" ?disabled=${this.enCours} @click=${this.clore}>
            Confirmer la clôture
          </button>
          <button class="annuler-cloture" @click=${()=>{this.clotureArmee=!1}}>
            Annuler
          </button>
        </div>
      `:I`
        <button class="clore-session" @click=${()=>{this.clotureArmee=!0}}>
          Clore la session
        </button>
      `}
    `;var s}render(){return I`
      ${this.enAttente>0?I`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:B}
      ${this.donnees?this.rendreCloture(this.donnees):this.rendreOuverture()}
      ${this.message?I`<p class="message">${this.message}</p>`:B}
    `}};function Re(e,t){const i=new Date(t.getFullYear(),t.getMonth(),t.getDate()+e);return`${String(i.getFullYear()).padStart(4,"0")}-${String(i.getMonth()+1).padStart(2,"0")}-${String(i.getDate()).padStart(2,"0")}`}je.styles=[we,a`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--hs-text); }
    .titre { margin: 0 0 8px; font-size: 1.2rem; }
    .explication, .resume, .magasin-retenu { margin: 4px 0; color: var(--hs-text-2); }
    .en-attente { text-align: center; color: var(--hs-text-2); font-size: 0.85rem; margin: 0 0 8px; }
    .pastilles { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
    .pastille {
      min-height: var(--hs-touch); min-width: var(--hs-touch); padding: 0 16px; border-radius: 24px; border: none;
      font-size: 1rem; background: var(--hs-surface-2); color: var(--hs-text);
    }
    .pastille.choisie { background: var(--hs-accent); color: var(--hs-on-accent); }
    .emporter-liste, .photographier {
      display: block; width: 100%; min-height: var(--hs-touch); font-size: 1.05rem; border-radius: 12px;
      border: none; margin: 8px 0; background: var(--hs-surface-2);
      color: var(--hs-text);
    }
    .magasin-label { display: block; margin: 8px 0; }
    .champ-magasin {
      min-height: var(--hs-touch); width: 100%; box-sizing: border-box; font-size: 1rem; padding: 4px 8px;
    }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .erreur { color: var(--hs-text); border-left: 3px solid var(--hs-danger); padding-left: 8px; font-size: 0.9rem; }
    .restantes { color: var(--hs-text); border-left: 3px solid var(--hs-danger); padding-left: 8px; font-size: 0.9rem; }
    .message { color: var(--hs-text-2); font-size: 0.9rem; }
    .ouvrir-session {
      display: block; width: 100%; min-height: var(--hs-touch); font-size: 1.2rem; border-radius: 12px;
      border: none; background: var(--hs-accent); color: var(--hs-on-accent);
      margin-top: 16px;
    }
    .ouvrir-session:disabled { opacity: 0.5; }
    .clore-session, .confirmer-cloture, .annuler-cloture {
      display: block; width: 100%; min-height: var(--hs-touch); font-size: 1.1rem; border-radius: 12px;
      border: none; margin-top: 12px;
    }
    .clore-session, .confirmer-cloture {
      background: var(--hs-surface); color: var(--hs-text); border: 2px solid var(--hs-danger);
    }
    .annuler-cloture {
      background: var(--hs-surface-2); color: var(--hs-text);
    }
    .confirmation-cloture { display: block; }
  `],e([pe({attribute:!1})],je.prototype,"donnees",void 0),e([pe({attribute:!1})],je.prototype,"connexion",void 0),e([pe({attribute:!1})],je.prototype,"file",void 0),e([pe({attribute:!1})],je.prototype,"enAttente",void 0),e([de()],je.prototype,"magasins",void 0),e([de()],je.prototype,"magasinChoisi",void 0),e([de()],je.prototype,"magasinSaisi",void 0),e([de()],je.prototype,"erreurMagasins",void 0),e([de()],je.prototype,"clotureArmee",void 0),e([de()],je.prototype,"enCours",void 0),e([de()],je.prototype,"message",void 0),je=e([ce("home-stock-session")],je);let Fe=class extends oe{constructor(){super(...arguments),this.lignes=[],this.enAttente=0,this.emplacements=[],this.erreurEmplacements=null,this.emplacementChoisi={},this.enCours=new Set,this.aEuDesLignes=!1,this.termineEnvoye=!1}connectedCallback(){super.connectedCallback(),this.chargerEmplacements()}willUpdate(e){e.has("lignes")&&this.lignes.length>0&&(this.aEuDesLignes=!0)}updated(){this.aEuDesLignes&&0===this.lignes.length&&!this.termineEnvoye&&(this.termineEnvoye=!0,this.dispatchEvent(new CustomEvent("termine",{bubbles:!0,composed:!0})))}async chargerEmplacements(){if(this.connexion){this.erreurEmplacements=null;try{const e=await this.connexion.appeler("home_stock/locations/list");this.emplacements=e.locations}catch{this.erreurEmplacements="Impossible de récupérer les emplacements. Vérifiez la connexion."}}}emplacementPour(e){const t=this.emplacementChoisi[String(e.id)];return void 0!==t?t:e.default_location_id}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()),i.sort.then(e=>"envoyee"===e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}ranger(e,t){const i=this.emplacementPour(e);if(null===i)return;const s=String(e.id);if(this.enCours.has(s))return;this.enCours=new Set(this.enCours).add(s);const r=()=>{const e=new Set(this.enCours);e.delete(s),this.enCours=e};"session"===e.source?this.ecrire("home_stock/session/store_line",{line_id:e.id,location_id:i,best_before:t.date}).then(r):this.ecrire("home_stock/stock/add",{article_id:e.article_id,quantity:e.quantity,location_id:i,best_before:t.date,price_per_base_unit:e.unit_price,idempotency_key:`rangement:${e.id}`}).then(t=>{r(),t&&this.dispatchEvent(new CustomEvent("ligne-autonome-rangee",{detail:{id:e.id},bubbles:!0,composed:!0}))})}rendreLigne(e){const t=String(e.id),i=this.enCours.has(t),s=this.emplacementPour(e),r=function(e,t){const i=[];t&&t>0&&i.push({libelle:`+${t} j (habituel)`,date:Re(t,e)}),i.push({libelle:"+3 j",date:Re(3,e)},{libelle:"+1 sem",date:Re(7,e)},{libelle:"+1 mois",date:Re(31,e)});const s=new Set,r=i.filter(e=>e.date&&!s.has(e.date)&&s.add(e.date));return[...r,{libelle:"Sans DLC",date:null}]}(new Date,e.default_shelf_life_days);return I`
      <article class="ligne">
        ${e.image?I`<img class="image" src=${e.image} alt="" />`:B}
        <div class="infos">
          <p class="nom">${function(e){return"session"===e.source?e.article_label??e.product_name:e.product_name}(e)}${e.brand?` — ${e.brand}`:""}</p>
          <p class="quantite">
            ${e.quantity}${"piece"!==e.base_unit?` ${e.base_unit}`:""}
          </p>
          <label class="emplacement-label">
            Emplacement
            <select class="emplacement-champ" .value=${null!==s?String(s):""}
              ?disabled=${i}
              @change=${e=>{this.emplacementChoisi={...this.emplacementChoisi,[t]:Number(e.target.value)}}}>
              ${null===s?I`
                <option value="" disabled selected>Choisir…</option>
              `:B}
              ${this.emplacements.map(e=>I`
                <option value=${String(e.id)} ?selected=${e.id===s}>${e.name}</option>
              `)}
            </select>
          </label>
          ${null===s?I`
            <p class="emplacement-manquant">Choisissez un emplacement avant de ranger.</p>
          `:B}
          ${this.erreurEmplacements?I`<p class="erreur">${this.erreurEmplacements}</p>`:B}
          <div class="raccourcis-dlc">
            ${r.map(t=>I`
              <button class="raccourci-dlc" ?disabled=${i||null===s}
                @click=${()=>this.ranger(e,t)}>
                ${i?"Rangement…":t.libelle}
              </button>
            `)}
          </div>
        </div>
      </article>
    `}render(){if(0===this.lignes.length)return I`<p class="tout-range">Tout est rangé.</p>`;const e=function(e,t,i=e=>e.default_location_id){const s=e=>null===e?"Emplacement à choisir":t.find(t=>t.id===e)?.name??"Emplacement à choisir",r=[];for(const t of e){const e=i(t);let n=r.find(t=>t.emplacementId===e);n||(n={emplacementId:e,nom:s(e),lignes:[]},r.push(n)),n.lignes.push(t)}return r}(this.lignes,this.emplacements,e=>this.emplacementPour(e));return I`
      ${this.enAttente>0?I`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:B}
      ${e.map(e=>I`
        <section class="emplacement">
          <h3 class="emplacement-nom">${e.nom}</h3>
          ${e.lignes.map(e=>this.rendreLigne(e))}
        </section>
      `)}
    `}};function Ve(e){const t=e.trim();if(""===t)return{ok:!0,valeur:null};const i=Number(t.replace(",","."));return Number.isFinite(i)?{ok:!0,valeur:i}:{ok:!1}}function Oe(e){return(Math.round(100*e)/100).toString().replace(".",",")}Fe.styles=[we,a`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--hs-text); }
    .tout-range { text-align: center; font-size: 1.2rem; margin-top: 32px; }
    .en-attente { text-align: center; color: var(--hs-text-2); font-size: 0.85rem; margin: 0 0 8px; }
    .emplacement-nom {
      margin: 16px 0 4px; font-size: 0.9rem; text-transform: uppercase;
      color: var(--hs-text-2); letter-spacing: 0.04em;
    }
    .ligne {
      display: flex; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--hs-divider);
    }
    .image { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; flex-shrink: 0; }
    .infos { flex: 1; min-width: 0; }
    .nom { margin: 0 0 4px; }
    .quantite { margin: 0 0 4px; color: var(--hs-text-2); }
    .emplacement-label { display: block; font-size: 0.85rem; margin-bottom: 8px; }
    .emplacement-champ { min-height: var(--hs-touch); width: 100%; box-sizing: border-box; font-size: 1rem; }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .emplacement-manquant {
      color: var(--hs-text); border-left: 3px solid var(--hs-danger);
      padding-left: 8px; font-size: 0.85rem; margin: 0 0 8px;
    }
    .erreur {
      color: var(--hs-text); border-left: 3px solid var(--hs-danger);
      padding-left: 8px; font-size: 0.85rem;
    }
    .raccourcis-dlc { display: flex; flex-wrap: wrap; gap: 8px; }
    .raccourci-dlc {
      min-height: var(--hs-touch); min-width: var(--hs-touch); padding: 0 12px; border-radius: 8px; border: none; font-size: 0.95rem;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .raccourci-dlc:disabled { opacity: 0.5; }
  `],e([pe({attribute:!1})],Fe.prototype,"lignes",void 0),e([pe({attribute:!1})],Fe.prototype,"connexion",void 0),e([pe({attribute:!1})],Fe.prototype,"file",void 0),e([pe({attribute:!1})],Fe.prototype,"enAttente",void 0),e([de()],Fe.prototype,"emplacements",void 0),e([de()],Fe.prototype,"erreurEmplacements",void 0),e([de()],Fe.prototype,"emplacementChoisi",void 0),e([de()],Fe.prototype,"enCours",void 0),Fe=e([ce("home-stock-rangement")],Fe);const Ne=[[1/4,"¼"],[1/3,"⅓"],[.5,"½"],[2/3,"⅔"],[3/4,"¾"]];const He={g:"g",ml:"ml",piece:""};function Te(e,t,i,s){if(null===e)return"";const r=s??i;return r?`${Oe(e)} ${function(e,t){if(t<2)return e;const[i,...s]=e.split(" ");return[i.endsWith("s")?i:`${i}s`,...s].join(" ")}(r,e)}`:"piece"===t?function(e){const t=Math.floor(e),i=e-t;if(i<.005)return String(t);for(const[e,s]of Ne)if(Math.abs(i-e)<.005)return 0===t?s:`${t} ${s}`;return Oe(e)}(e):`${Oe(e)} ${He[t]}`.trim()}function De(e){return{name:e.name,aisle_id:null!==e.aisle_id?String(e.aisle_id):"",default_location_id:null!==e.default_location_id?String(e.default_location_id):"",min_quantity:null!==e.min_quantity?String(e.min_quantity):"",default_shelf_life_days:null!==e.default_shelf_life_days?String(e.default_shelf_life_days):"",manual_portion:null!==e.manual_portion?String(e.manual_portion):""}}function Ie(e){const t=e.trim();return""===t?null:Number(t)}const Ue={min_quantity:"Seuil de réapprovisionnement",default_shelf_life_days:"Durée de conservation",manual_portion:"Ma portion"};function Be(e,t,i,s){const r=Ve(t[e]);return r.ok?(r.valeur!==i[e]&&(s[e]=r.valeur),null):`${Ue[e]} : nombre invalide (« ${t[e]} »).`}let Je=class extends oe{constructor(){super(...arguments),this.large=!1,this.enAttente=0,this.produits=[],this.rayons=[],this.emplacements=[],this.quantitesParProduit={},this.erreurChargement=null,this.recherche="",this.produitEditeId=null,this.produitEnEdition=null,this.brouillon=null,this.erreurEdition=null,this.enCours=!1,this.enAttenteEnvoi=!1,this.nomRayon=e=>null===e?"Sans rayon":this.rayons.find(t=>t.id===e)?.name??"Sans rayon"}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(this.connexion){this.erreurChargement=null;try{const[e,t,i,s]=await Promise.all([this.connexion.appeler("home_stock/products/list"),this.connexion.appeler("home_stock/aisles/list"),this.connexion.appeler("home_stock/locations/list"),this.connexion.appeler("home_stock/batches/list")]);this.produits=e.products,this.rayons=t.aisles,this.emplacements=i.locations;const r={};for(const e of s.batches)r[e.product_id]=(r[e.product_id]??0)+e.remaining;this.quantitesParProduit=r}catch{this.erreurChargement="Impossible de récupérer le catalogue. Vérifiez la connexion."}}}nomEmplacement(e){return null===e?"Aucun":this.emplacements.find(t=>t.id===e)?.name??"Aucun"}get produitsFiltres(){return function(e,t,i){const s=t.trim().toLowerCase();return s?e.filter(e=>e.name.toLowerCase().includes(s)||i(e.aisle_id).toLowerCase().includes(s)):e}(this.produits,this.recherche,this.nomRayon)}async ouvrirEdition(e){if(this.produitEditeId=e.id,this.produitEnEdition=e,this.brouillon=De(e),this.erreurEdition=null,this.enAttenteEnvoi=!1,this.connexion)try{const t=await this.connexion.appeler("home_stock/product/get",{product_id:e.id});this.produitEditeId===e.id&&(this.produitEnEdition=t.product,this.brouillon=De(t.product))}catch{}}fermerEdition(){this.produitEditeId=null,this.produitEnEdition=null,this.brouillon=null,this.erreurEdition=null,this.enAttenteEnvoi=!1}modifierBrouillon(e,t){this.brouillon&&(this.brouillon={...this.brouillon,[e]:t})}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()),i.sort.then(e=>"envoyee"===e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}mangerProduit(e){this.dispatchEvent(new CustomEvent("manger-produit",{detail:{product_id:e.id},bubbles:!0,composed:!0}))}async enregistrer(){const e=this.produitEnEdition,t=this.brouillon;if(!e||!t||this.enCours)return;const i=function(e,t){const i={},s=e.name.trim();s&&s!==t.name&&(i.name=s),Ie(e.aisle_id)!==t.aisle_id&&(i.aisle_id=Ie(e.aisle_id)),Ie(e.default_location_id)!==t.default_location_id&&(i.default_location_id=Ie(e.default_location_id));const r=Be("min_quantity",e,t,i);if(r)return{ok:!1,erreur:r};const n=Be("default_shelf_life_days",e,t,i);if(n)return{ok:!1,erreur:n};const a=Be("manual_portion",e,t,i);return a?{ok:!1,erreur:a}:{ok:!0,champs:i}}(t,e);if(!i.ok)return void(this.erreurEdition=i.erreur);if(0===Object.keys(i.champs).length)return void this.fermerEdition();this.enCours=!0,this.erreurEdition=null,this.enAttenteEnvoi=!1;const s=await this.ecrire("home_stock/product/update",{product_id:e.id,fields:i.champs});this.enCours=!1,s?(await this.charger(),this.fermerEdition()):this.enAttenteEnvoi=!0}rendreEdition(e){const t=this.brouillon;return t?I`
      <div class="edition">
        <label class="champ">
          Nom
          <input class="champ-nom" .value=${t.name}
            @input=${e=>this.modifierBrouillon("name",e.target.value)} />
        </label>
        <label class="champ">
          Rayon
          <select class="champ-rayon" .value=${t.aisle_id}
            @change=${e=>this.modifierBrouillon("aisle_id",e.target.value)}>
            <option value="">Sans rayon</option>
            ${this.rayons.map(e=>I`<option value=${String(e.id)}>${e.name}</option>`)}
          </select>
        </label>
        <label class="champ">
          Emplacement par défaut
          <select class="champ-emplacement" .value=${t.default_location_id}
            @change=${e=>this.modifierBrouillon("default_location_id",e.target.value)}>
            <option value="">Aucun</option>
            ${this.emplacements.map(e=>I`<option value=${String(e.id)}>${e.name}</option>`)}
          </select>
        </label>
        <label class="champ">
          Seuil de réapprovisionnement${"piece"!==e.base_unit?` (${e.base_unit})`:""}
          <input class="champ-seuil" inputmode="decimal" placeholder="ex. 200" .value=${t.min_quantity}
            @input=${e=>this.modifierBrouillon("min_quantity",e.target.value)} />
        </label>
        <label class="champ">
          Durée de conservation (jours)
          <input class="champ-conservation" inputmode="decimal" placeholder="ex. 5" .value=${t.default_shelf_life_days}
            @input=${e=>this.modifierBrouillon("default_shelf_life_days",e.target.value)} />
        </label>
        ${"piece"!==e.base_unit?I`
          <label class="champ">
            Ma portion (${e.base_unit})
            <input class="champ-portion" inputmode="decimal" placeholder="ex. 45" .value=${t.manual_portion}
              @input=${e=>this.modifierBrouillon("manual_portion",e.target.value)} />
            <span class="mention">vide = déduite automatiquement</span>
          </label>
        `:B}
        <p class="champ-lecture-seule">
          Catégorie : ${e.category_id??"aucune"} (identifiant interne) — non modifiable ici : aucune
          liste de noms n'existe côté serveur pour vérifier une saisie.
        </p>
        <p class="champ-lecture-seule">
          Unité de base : ${"piece"===e.base_unit?"à la pièce":e.base_unit}
          — se change uniquement par une conversion, pas depuis cet écran.
        </p>
        ${this.enAttenteEnvoi?I`
          <p class="etat-envoi">Enregistrement en file d'attente (hors ligne) ou refusé — voir le message ci-dessus.</p>
        `:B}
        ${this.erreurEdition?I`<p class="erreur">${this.erreurEdition}</p>`:B}
        <div class="actions-edition">
          <button class="enregistrer" ?disabled=${this.enCours} @click=${this.enregistrer}>
            ${this.enCours?"Enregistrement…":"Enregistrer"}
          </button>
          <button class="annuler" ?disabled=${this.enCours} @click=${()=>this.fermerEdition()}>Annuler</button>
        </div>
      </div>
    `:B}rendreLigne(e){const t=this.quantitesParProduit[e.id]??0,i="piece"!==e.base_unit?` ${e.base_unit}`:"";return I`
      <article class="ligne">
        <div class="infos">
          <p class="nom">${e.name}</p>
          <p class="meta">
            ${this.nomRayon(e.aisle_id)} · en stock : ${t}${i}
            ${null!==e.min_quantity?I` · seuil : ${e.min_quantity}${i}`:B}
            · emplacement : ${this.nomEmplacement(e.default_location_id)}
          </p>
        </div>
        <button class="manger" @click=${()=>this.mangerProduit(e)}>Manger</button>
        <button class="modifier" @click=${()=>this.ouvrirEdition(e)}>Modifier</button>
        ${this.produitEditeId===e.id?this.rendreEdition(this.produitEnEdition??e):B}
      </article>
    `}rendreLigneTableau(e){const t="piece"!==e.base_unit?` ${e.base_unit}`:"";return I`
      <tr class="ligne ${this.produitEditeId===e.id?"ligne-editee":""}">
        <td class="nom">${e.name}</td>
        <td class="cellule-unite">${"piece"===e.base_unit?"à la pièce":e.base_unit}</td>
        <td class="cellule-seuil">${null!==e.min_quantity?`${e.min_quantity}${t}`:"—"}</td>
        <td class="cellule-categorie">${e.category_id??"—"}</td>
        <td class="cellule-conservation">${null!==e.default_shelf_life_days?`${e.default_shelf_life_days} j`:"—"}</td>
        <td class="cellule-actions">
          <button class="manger" @click=${()=>this.mangerProduit(e)}>Manger</button>
          <button class="modifier" @click=${()=>this.ouvrirEdition(e)}>Modifier</button>
        </td>
      </tr>
    `}rendreEntete(){return I`
      <input class="recherche" type="search" placeholder="Rechercher un produit ou un rayon…"
        .value=${this.recherche}
        @input=${e=>{this.recherche=e.target.value}} />

      ${this.enAttente>0?I`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:B}

      ${this.erreurChargement?I`
        <p class="erreur">${this.erreurChargement}</p>
        <button class="reessayer" @click=${()=>{this.charger()}}>Réessayer</button>
      `:B}

      ${this.erreurChargement||0!==this.produitsFiltres.length?B:I`
        <p class="vide">Aucun produit.</p>
      `}
    `}rendreDense(){const e=this.produitEnEdition;return I`
      ${this.rendreEntete()}
      <div class="dense">
        <table class="tableau">
          <thead>
            <tr>
              <th>Nom</th><th>Unité</th><th>Seuil</th><th>Catégorie</th>
              <th>Conservation</th><th class="colonne-actions"></th>
            </tr>
          </thead>
          <tbody>${this.produitsFiltres.map(e=>this.rendreLigneTableau(e))}</tbody>
        </table>
        ${null!==e?I`
          <aside class="volet-edition">${this.rendreEdition(e)}</aside>
        `:B}
      </div>
    `}render(){return this.large?this.rendreDense():I`
      ${this.rendreEntete()}
      <div class="liste">
        ${this.produitsFiltres.map(e=>this.rendreLigne(e))}
      </div>
    `}};Je.styles=[we,a`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--hs-text); }
    .recherche {
      display: block; width: 100%; min-height: var(--hs-touch); box-sizing: border-box; font-size: 1rem;
      padding: 4px 12px; border-radius: 8px; border: 1px solid var(--hs-divider); margin-bottom: 8px;
    }
    .en-attente { text-align: center; color: var(--hs-text-2); font-size: 0.85rem; margin: 0 0 8px; }
    .vide { color: var(--hs-text-2); text-align: center; }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .erreur { color: var(--hs-text); border-left: 3px solid var(--hs-danger); padding-left: 8px; font-size: 0.9rem; }
    .reessayer {
      min-height: var(--hs-touch); width: 100%; border-radius: 8px; border: none;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .ligne {
      display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--hs-divider);
    }
    .infos { flex: 1; min-width: 0; }
    .nom { margin: 0 0 4px; font-weight: 600; }
    .meta { margin: 0; color: var(--hs-text-2); font-size: 0.85rem; }
    .modifier {
      min-height: var(--hs-touch); min-width: var(--hs-touch); padding: 0 16px; border-radius: 8px; border: none;
      background: var(--hs-accent); color: var(--hs-on-accent); flex-shrink: 0;
    }
    .manger {
      min-height: var(--hs-touch); min-width: var(--hs-touch); padding: 0 16px; border-radius: 8px; border: none;
      background: var(--hs-surface-2); color: var(--hs-text); flex-shrink: 0;
    }
    .edition {
      flex: 1 0 100%; display: flex; flex-direction: column; gap: 8px; margin-top: 8px;
      padding: 12px; border-radius: 8px; background: var(--hs-surface-2);
      box-sizing: border-box;
    }
    .champ { display: block; font-size: 0.85rem; }
    .champ-nom, .champ-rayon, .champ-emplacement, .champ-seuil, .champ-conservation {
      display: block; width: 100%; min-height: var(--hs-touch); box-sizing: border-box; font-size: 1rem;
      padding: 4px 8px; margin-top: 4px;
    }
    .champ-lecture-seule { color: var(--hs-text-2); font-size: 0.85rem; margin: 4px 0; }
    .etat-envoi { color: var(--hs-text-2); font-size: 0.85rem; }
    .actions-edition { display: flex; flex-wrap: wrap; gap: 8px; }
    .enregistrer, .annuler {
      min-height: var(--hs-touch); flex: 1; border-radius: 8px; border: none; font-size: 0.95rem;
    }
    .enregistrer { background: var(--hs-accent); color: var(--hs-on-accent); }
    .enregistrer:disabled { opacity: 0.5; }
    .annuler { background: var(--hs-surface-2); color: var(--hs-text); border: 1px solid var(--hs-divider); }

    /* --- la vue dense (lot 6), au-delà de 1000 px --------------------------
       La liste reste ENTIÈREMENT visible pendant l'édition : le volet se pose
       à côté, jamais par-dessus. Sa largeur est bornée pour que le tableau ne
       se réduise pas à rien sur un 1280, et que le texte ne s'étire pas sur un
       1920 — les deux défauts que les trois formats du vérificateur mesurent. */
    .dense { display: flex; align-items: flex-start; gap: 16px; }
    .tableau { flex: 1 1 auto; min-width: 0; border-collapse: collapse; table-layout: fixed; }
    .tableau th, .tableau td {
      text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--hs-divider);
      overflow-wrap: anywhere;
    }
    .tableau th { font-size: 0.85rem; color: var(--hs-text-2); font-weight: 600; }
    .tableau .nom { font-weight: 600; }
    .tableau .ligne { height: 48px; }
    .ligne-editee { background: var(--hs-surface-2); }
    .cellule-actions { white-space: nowrap; width: 1%; }
    .cellule-actions .manger, .cellule-actions .modifier { padding: 0 12px; }
    .volet-edition {
      flex: 0 0 320px; position: sticky; top: 12px;
      max-height: calc(100vh - 24px); overflow-y: auto;
    }
    .volet-edition .edition { margin-top: 0; }
  `],e([pe({attribute:!1})],Je.prototype,"connexion",void 0),e([pe({type:Boolean})],Je.prototype,"large",void 0),e([pe({attribute:!1})],Je.prototype,"file",void 0),e([pe({attribute:!1})],Je.prototype,"enAttente",void 0),e([de()],Je.prototype,"produits",void 0),e([de()],Je.prototype,"rayons",void 0),e([de()],Je.prototype,"emplacements",void 0),e([de()],Je.prototype,"quantitesParProduit",void 0),e([de()],Je.prototype,"erreurChargement",void 0),e([de()],Je.prototype,"recherche",void 0),e([de()],Je.prototype,"produitEditeId",void 0),e([de()],Je.prototype,"produitEnEdition",void 0),e([de()],Je.prototype,"brouillon",void 0),e([de()],Je.prototype,"erreurEdition",void 0),e([de()],Je.prototype,"enCours",void 0),e([de()],Je.prototype,"enAttenteEnvoi",void 0),Je=e([ce("home-stock-catalogue")],Je);const Qe=new Set(["Une resynchronisation Open Food Facts est déjà en cours."]),Ze={ok:"conforme",empty:"rien mesuré — ce contrôle n'a rien pu comparer",gap:"écart",unacknowledged:"à acquitter, un par un"};function Ge(e,t,i){const s=t+i;if(s<0||s>=e.length)return null;const r=[...e];return[r[t],r[s]]=[r[s],r[t]],r}let We=class extends oe{constructor(){super(...arguments),this.large=!1,this.enAttente=0,this.rayons=[],this.emplacements=[],this.erreurChargement=null,this.magasins=[],this.magasinOuvert=null,this.parcours=null,this.fusionArmee=null,this.erreurFusion=null,this.recurrentes=[],this.saisieRecurrente="",this.saisieJours="",this.agentTicket=null,this.tailleTickets=null,this.bascule=null,this.basculeEnCours=!1,this.erreurBascule=null,this.resyncEnCours=!1,this.messageResync=null,this.erreurResync=null}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(this.connexion){this.erreurChargement=null;try{const[e,t,i,s]=await Promise.all([this.connexion.appeler("home_stock/aisles/list"),this.connexion.appeler("home_stock/locations/list"),this.connexion.appeler("home_stock/stores/list"),this.connexion.appeler("home_stock/recurring/list")]);this.rayons=e?.aisles??[],this.emplacements=t?.locations??[],this.magasins=i?.stores??[],this.recurrentes=s?.recurring??[]}catch{this.erreurChargement="Impossible de récupérer les rayons et les emplacements. Vérifiez la connexion."}}}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}async deplacerRayon(e,t){const i=Ge(this.rayons,e,t);if(null===i)return;if(this.rayons=i,!this.file)return;const s=this.file.ajouter("home_stock/aisles/reorder",{aisle_ids:i.map(e=>e.id)});this.avertirFile(),await this.file.rejouer(),this.avertirFile(),"refusee"===await s.sort&&await this.charger()}async resynchroniser(){if(this.connexion&&!this.resyncEnCours){this.resyncEnCours=!0,this.messageResync=null,this.erreurResync=null;try{await this.connexion.appelerService("home_stock","resync_off",{all:!0}),this.messageResync="Resynchronisation lancée en tâche de fond — environ 40 minutes pour tout le catalogue. Les champs corrigés à la main ne sont jamais écrasés."}catch(e){this.erreurResync=function(e){const t=e&&"object"==typeof e&&"message"in e&&"string"==typeof e.message?e.message:null;return null!==t&&Qe.has(t)?t:"La resynchronisation n'a pas pu être lancée."}(e)}finally{this.resyncEnCours=!1}}}async controlerBascule(){if(this.connexion&&!this.basculeEnCours){this.basculeEnCours=!0,this.erreurBascule=null;try{this.bascule=await this.connexion.appeler("home_stock/migration/check",{archive:!1})}catch{this.bascule=null,this.erreurBascule="Le contrôle n'a pas pu être lancé."}finally{this.basculeEnCours=!1}}}rendreBascule(){if(this.basculeEnCours)return I`<p class="explication">Contrôle en cours…</p>`;if(!this.bascule)return B;const e=this.bascule.blocking.length;return I`
      <p class="verdict-bascule">
        ${0===e?"Aucun contrôle bloquant : la bascule peut continuer.":`${e} contrôles bloquants : ne pas continuer.`}
      </p>
      <ul class="liste-controles">
        ${this.bascule.checks.map(e=>I`
          <li class="controle ${e.blocking?"bloquant":""}"
              data-code=${e.code}>
            <span class="controle-code">${e.code}</span>
            <span class="controle-label">${e.label}</span>
            <span class="controle-chiffres">
              ${"empty"===e.verdict?Ze.empty:`${e.grocy_count} chez Grocy, ${e.home_count} ici — ${Ze[e.verdict]} : ${e.gap}`}
            </span>
            ${e.details.length>0?I`
              <span class="controle-details">${e.details[0]}</span>
            `:B}
          </li>
        `)}
      </ul>
    `}rendreRayons(){return 0===this.rayons.length?I`<p class="vide">Aucun rayon.</p>`:I`
      <ul class="liste-rayons">
        ${this.rayons.map((e,t)=>I`
          <li class="rayon">
            <span class="rayon-nom">${e.name}</span>
            <span class="rayon-boutons">
              <button class="monter" aria-label="Monter ${e.name}" ?disabled=${0===t}
                @click=${()=>{this.deplacerRayon(t,-1)}}>▲</button>
              <button class="descendre" aria-label="Descendre ${e.name}"
                ?disabled=${t===this.rayons.length-1}
                @click=${()=>{this.deplacerRayon(t,1)}}>▼</button>
            </span>
          </li>
        `)}
      </ul>
    `}async ouvrirMagasin(e){if(this.fusionArmee=null,this.erreurFusion=null,this.magasinOuvert===e.id)return this.magasinOuvert=null,void(this.parcours=null);this.magasinOuvert=e.id,this.parcours=null,this.connexion&&(this.parcours=await this.connexion.appeler("home_stock/store/aisles",{store_id:e.id}))}async deplacerRayonMagasin(e,t){const i=this.parcours;if(!i||!this.connexion)return;const s=Ge(i.aisles,e,t);null!==s&&(this.parcours=await this.connexion.appeler("home_stock/store/reorder_aisles",{store_id:i.store_id,aisle_ids:s.map(e=>e.aisle_id)}))}async reprendreApprentissage(e){const t=this.parcours;t&&this.connexion&&(this.parcours=await this.connexion.appeler("home_stock/store/unpin_aisle",{store_id:t.store_id,aisle_id:e}))}async fusionner(e){const t=this.magasins.find(t=>t.id!==e);if(t&&this.connexion){this.erreurFusion=null;try{const i=await this.connexion.appeler("home_stock/store/merge",{keep_id:t.id,merge_id:e});this.magasins=i.stores}catch(e){this.erreurFusion=e?.message??"Fusion impossible."}this.fusionArmee=null}}async enregistrerRecurrente(){const e=this.saisieRecurrente.trim(),t=Number.parseInt(this.saisieJours,10);if(!e||!Number.isFinite(t)||!this.connexion)return;const i=await this.connexion.appeler("home_stock/recurring/save",{free_text:e,every_days:t});this.recurrentes=i.recurring,this.saisieRecurrente="",this.saisieJours=""}async supprimerRecurrente(e){if(!this.connexion)return;const t=await this.connexion.appeler("home_stock/recurring/delete",{recurring_id:e});this.recurrentes=t.recurring}rendreMagasins(){return 0===this.magasins.length?I`<p class="vide">Aucun magasin connu.</p>`:I`
      <ul class="liste-magasins">
        ${this.magasins.map(e=>I`
          <li class="magasin">
            <button class="magasin-onglet"
              aria-pressed=${this.magasinOuvert===e.id?"true":"false"}
              @click=${()=>{this.ouvrirMagasin(e)}}>
              ${e.name}
            </button>
            ${this.magasins.length>1?I`
              ${this.fusionArmee===e.id?I`
                <button class="confirmer-fusion"
                  @click=${()=>{this.fusionner(e.id)}}>Confirmer</button>
                <button class="annuler-fusion"
                  @click=${()=>{this.fusionArmee=null}}>Annuler</button>
              `:I`
                <button class="fusionner"
                  @click=${()=>{this.fusionArmee=e.id}}>Fusionner</button>
              `}
            `:B}
            ${this.magasinOuvert===e.id?this.rendreParcours():B}
          </li>
        `)}
      </ul>
      ${this.erreurFusion?I`<p class="erreur-fusion">${this.erreurFusion}</p>`:B}
    `}rendreParcours(){const e=this.parcours;return e?I`
      <p class="fiabilite">${e.reliable?`Ordre appris de ce magasin (${e.observed_sessions} sessions).`:`${e.observed_sessions} session${e.observed_sessions>1?"s":""} sur ${e.required_sessions} : l’ordre par défaut est encore utilisé.`}</p>
      <ul class="liste-rayons-magasin">
        ${e.aisles.map((t,i)=>I`
          <li class="rayon-magasin ${"manual"===t.source?"epingle":""}">
            <span class="rayon-magasin-nom">${t.aisle_name}</span>
            ${"manual"===t.source?I`
              <span class="marque-epingle">épinglé</span>
              <button class="reprendre-apprentissage"
                @click=${()=>{this.reprendreApprentissage(t.aisle_id)}}>
                Reprendre l’apprentissage
              </button>
            `:B}
            <button class="monter-rayon-magasin" aria-label="Monter ${t.aisle_name}"
              ?disabled=${0===i}
              @click=${()=>{this.deplacerRayonMagasin(i,-1)}}>▲</button>
            <button class="descendre-rayon-magasin" aria-label="Descendre ${t.aisle_name}"
              ?disabled=${i===e.aisles.length-1}
              @click=${()=>{this.deplacerRayonMagasin(i,1)}}>▼</button>
          </li>
        `)}
      </ul>
    `:I`<p class="vide">Chargement du parcours…</p>`}rendreRecurrentes(){return I`
      <ul class="liste-recurrentes">
        ${this.recurrentes.map(e=>I`
          <li class="recurrente">
            <span class="recurrente-nom">${e.product_name??e.free_text}</span>
            <span class="recurrente-jours">${`tous les ${e.every_days} j`}</span>
            <button class="supprimer-recurrente"
              aria-label=${`Supprimer ${e.product_name??e.free_text}`}
              @click=${()=>{this.supprimerRecurrente(e.id)}}>×</button>
          </li>
        `)}
      </ul>
      <div class="ajout-recurrente">
        <input class="champ-recurrente" placeholder="Ce qu’on rachète" .value=${this.saisieRecurrente}
          aria-label="Libellé de la ligne récurrente"
          @input=${e=>{this.saisieRecurrente=e.target.value}} />
        <input class="champ-jours" inputmode="numeric" placeholder="jours" .value=${this.saisieJours}
          aria-label="Tous les combien de jours"
          @input=${e=>{this.saisieJours=e.target.value}} />
        <button class="ajouter-recurrente"
          @click=${()=>{this.enregistrerRecurrente()}}>Ajouter</button>
      </div>
    `}rendreEmplacements(){return 0===this.emplacements.length?I`<p class="vide">Aucun emplacement.</p>`:I`
      <ul class="liste-emplacements">
        ${this.emplacements.map(e=>I`
          <li class="emplacement">
            <span class="emplacement-nom">${e.name}</span>
            <span class="emplacement-type">${e.kind}</span>
          </li>
        `)}
      </ul>
    `}render(){const e=I`
      <section class="section">
        <h3 class="titre">Ordre des rayons</h3>
        <p class="explication">
          L'ordre du parcours en magasin — utilisé pour trier le panier. Pas de glisser-déposer :
          « monter » et « descendre » déplacent un rayon d'un cran.
        </p>
        ${this.rendreRayons()}
      </section>

      <section class="section">
        <h3 class="titre">Magasins et parcours</h3>
        <p class="explication">
          L'ordre appris de chaque magasin. Déplacer un rayon l'épingle : l'apprentissage
          ne le déplacera plus. Fusionner deux enseignes réunit leurs sessions, leurs prix
          et leurs parcours — et ne réécrit jamais ce qui a été observé.
        </p>
        ${this.rendreMagasins()}
      </section>

      <section class="section">
        <h3 class="titre">Achats récurrents</h3>
        <p class="explication">
          Ce qu'on rachète sans que rien ne le réclame : le café, les sacs poubelle.
        </p>
        ${this.rendreRecurrentes()}
      </section>

      <section class="section">
        <h3 class="titre">Tickets de caisse</h3>
        <p class="agent-ticket">${this.agentTicket?`Lus par ${this.agentTicket}.`:"Aucune entité de lecture configurée : choisissez-en une dans les options de l’intégration pour photographier vos tickets."}</p>
        <p class="taille-tickets">${this.tailleTickets?`Le dossier des photos pèse ${this.tailleTickets}. Les photos ne sont jamais supprimées automatiquement : elles justifient ce qui en a été tiré.`:"Les photos ne sont jamais supprimées automatiquement : elles justifient ce qui en a été tiré."}</p>
      </section>

      <section class="section">
        <h3 class="titre">Emplacements</h3>
        ${this.rendreEmplacements()}
      </section>

      <section class="section">
        <h3 class="titre">Open Food Facts</h3>
        <p class="explication">
          Relit tout le catalogue depuis Open Food Facts — environ 40 minutes au rythme qu'OFF tolère.
          Les champs corrigés à la main ne sont jamais écrasés.
        </p>
        <button class="resynchroniser" ?disabled=${this.resyncEnCours} @click=${this.resynchroniser}>
          ${this.resyncEnCours?"Lancement…":"Resynchroniser Open Food Facts"}
        </button>
        ${this.messageResync?I`<p class="message-resync">${this.messageResync}</p>`:B}
        ${this.erreurResync?I`<p class="erreur">${this.erreurResync}</p>`:B}
      </section>

      <section class="section">
        <h3 class="titre">Bascule</h3>
        <p class="explication">
          Où en est la reprise de Grocy. Ce bloc MONTRE l'état de la bascule ; il ne
          la conduit pas : les imports se lancent une fois depuis Outils de
          développement, et les acquittements se font nommément par le service.
        </p>
        <button class="controler" ?disabled=${this.basculeEnCours}
                @click=${this.controlerBascule}>Contrôler</button>
        ${this.rendreBascule()}
        ${this.erreurBascule?I`<p class="erreur">${this.erreurBascule}</p>`:B}
      </section>
    `;return I`
      ${this.enAttente>0?I`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:B}

      ${this.erreurChargement?I`
        <p class="erreur">${this.erreurChargement}</p>
        <button class="reessayer" @click=${()=>{this.charger()}}>Réessayer</button>
      `:B}

      ${this.large?I`<div class="trois-colonnes">${e}</div>`:e}
    `}};function Ye(e,t){return"piece"===t?`${Oe(e)} pièce${e>=2?"s":""}`:"g"===t?e>=1e3?`${Oe(e/1e3)} kg`:`${Oe(e)} g`:e>=1e3?`${Oe(e/1e3)} l`:`${Oe(e)} ml`}We.styles=[we,a`
    /* --- la vue dense (lot 6), au-delà de 1000 px --------------------------
       Trois colonnes d'au moins 320 px : en dessous, les explications de
       chaque section se cassent en lignes de trois mots. Le remplissage
       automatique laisse le nombre de colonnes suivre la largeur réelle, donc
       trois sur un 1280 et davantage sur un 1920, sans jamais étirer une
       section sur toute la page. */
    .trois-colonnes {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 0 24px; align-items: start;
    }
    .liste-magasins, .liste-rayons-magasin, .liste-recurrentes {
      list-style: none; margin: 0; padding: 0;
    }
    .magasin, .rayon-magasin, .recurrente {
      display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--hs-divider);
    }
    .magasin-onglet, .fusionner, .confirmer-fusion, .annuler-fusion,
    .monter-rayon-magasin, .descendre-rayon-magasin, .reprendre-apprentissage,
    .supprimer-recurrente, .ajouter-recurrente {
      min-height: var(--hs-touch); min-width: var(--hs-touch); border-radius: 8px; border: none; font-size: 0.9rem;
      background: var(--hs-surface-2); color: var(--hs-text);
    }
    .magasin-onglet[aria-pressed='true'] {
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .magasin-onglet, .rayon-magasin-nom, .recurrente-nom { flex: 1 1 auto; }
    .marque-epingle { font-size: 0.8rem; color: var(--hs-text-2); }
    .fiabilite { flex-basis: 100%; margin: 4px 0; font-size: 0.85rem; color: var(--hs-text-2); }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .erreur-fusion {
      color: var(--hs-text); border-left: 3px solid var(--hs-danger);
      padding-left: 8px; font-size: 0.9rem; margin: 8px 0 0;
    }
    .ajout-recurrente { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
    .champ-recurrente { flex: 1 1 140px; min-height: var(--hs-touch); box-sizing: border-box; padding: 4px 8px; }
    .champ-jours { flex: 0 0 88px; min-height: var(--hs-touch); box-sizing: border-box; padding: 4px 8px; }
    .agent-ticket, .taille-tickets { margin: 4px 0; color: var(--hs-text-2); font-size: 0.9rem; }
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--hs-text); }
    .en-attente { text-align: center; color: var(--hs-text-2); font-size: 0.85rem; margin: 0 0 8px; }
    .erreur {
      color: var(--hs-text); border-left: 3px solid var(--hs-danger); padding-left: 8px; font-size: 0.9rem;
    }
    .reessayer {
      min-height: var(--hs-touch); width: 100%; border-radius: 8px; border: none;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .section {
      margin: 0 0 20px; padding: 12px; border-radius: 8px; background: var(--hs-surface-2);
    }
    .titre { margin: 0 0 4px; font-size: 1rem; }
    .explication { margin: 0 0 8px; color: var(--hs-text-2); font-size: 0.85rem; }
    .vide { color: var(--hs-text-2); }
    .liste-rayons, .liste-emplacements { list-style: none; margin: 0; padding: 0; }
    .rayon, .emplacement {
      display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px;
      padding: 8px 0; border-bottom: 1px solid var(--hs-divider);
    }
    .rayon:last-child, .emplacement:last-child { border-bottom: none; }
    .rayon-nom, .emplacement-nom { flex: 1; min-width: 0; }
    .emplacement-type { color: var(--hs-text-2); font-size: 0.85rem; }
    .rayon-boutons { display: flex; gap: 8px; flex-shrink: 0; }
    .monter, .descendre {
      min-width: var(--hs-touch); min-height: var(--hs-touch); border-radius: 8px; border: none; font-size: 1.1rem;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .monter:disabled, .descendre:disabled { opacity: 0.4; }
    .resynchroniser {
      display: block; width: 100%; min-height: var(--hs-touch); border-radius: 8px; border: none; font-size: 0.95rem;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .resynchroniser:disabled { opacity: 0.6; }
    .message-resync { color: var(--hs-text-2); font-size: 0.85rem; margin: 8px 0 0; }
    .controler {
      display: block; width: 100%; min-height: var(--hs-touch); border-radius: 8px; border: none;
      font-size: 0.95rem;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .controler:disabled { opacity: 0.6; }
    .verdict-bascule { margin: 12px 0 4px; font-weight: 600; }
    .liste-controles { list-style: none; margin: 0; padding: 0; }
    .controle {
      display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px;
      padding: 6px 0; border-bottom: 1px solid var(--hs-divider);
      font-size: 0.9rem;
    }
    .controle:last-child { border-bottom: none; }
    .controle-code { font-weight: 700; min-width: 2.5em; }
    .controle-label { flex: 1; min-width: 0; }
    .controle-chiffres { color: var(--hs-text-2); }
    .controle-details { flex-basis: 100%; color: var(--hs-text-2); font-size: 0.85rem; }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le rouge d'un bloquant se dit
       par une bordure, le texte restant --hs-text sur les trois palettes. */
    .controle.bloquant { color: var(--hs-text); border-left: 3px solid var(--hs-danger); padding-left: 8px; }
    .controle.bloquant .controle-chiffres,
    .controle.bloquant .controle-details { color: var(--hs-text); }
  `],e([pe({attribute:!1})],We.prototype,"connexion",void 0),e([pe({type:Boolean})],We.prototype,"large",void 0),e([pe({attribute:!1})],We.prototype,"file",void 0),e([pe({attribute:!1})],We.prototype,"enAttente",void 0),e([de()],We.prototype,"rayons",void 0),e([de()],We.prototype,"emplacements",void 0),e([de()],We.prototype,"erreurChargement",void 0),e([de()],We.prototype,"magasins",void 0),e([de()],We.prototype,"magasinOuvert",void 0),e([de()],We.prototype,"parcours",void 0),e([de()],We.prototype,"fusionArmee",void 0),e([de()],We.prototype,"erreurFusion",void 0),e([de()],We.prototype,"recurrentes",void 0),e([de()],We.prototype,"saisieRecurrente",void 0),e([de()],We.prototype,"saisieJours",void 0),e([pe({attribute:!1})],We.prototype,"agentTicket",void 0),e([pe({attribute:!1})],We.prototype,"tailleTickets",void 0),e([de()],We.prototype,"bascule",void 0),e([de()],We.prototype,"basculeEnCours",void 0),e([de()],We.prototype,"erreurBascule",void 0),e([de()],We.prototype,"resyncEnCours",void 0),e([de()],We.prototype,"messageResync",void 0),e([de()],We.prototype,"erreurResync",void 0),We=e([ce("home-stock-reglages")],We);const Ke={yellow:"Bac jaune",glass:"Bac à verre",household:"Ordures ménagères",dropoff:"Déchèterie"};const Xe={consumption:"Mangé",waste:"Jeté",expired:"Périmé"};let et=class extends oe{constructor(){super(...arguments),this.productId=null,this.produit=null,this.lot=null,this.portion=null,this.portionSource=null,this.emballage=null,this.quantite=null,this.motif="consumption",this.partage=!1,this.partsTotal=2,this.partsMoi=1,this.erreur=null,this.enCours=!1,this.enAttenteEnvoi=!1,this.texteQuantite=""}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(!this.connexion||null===this.productId)return;const e=await this.connexion.appeler("home_stock/product/get",{product_id:this.productId});this.produit=e.produit??e.product,this.lot=e.next_batch,this.portion=e.suggested_portion,this.portionSource=e.portion_source??null,this.emballage=e.packaging??null,this.quantite="piece"===this.produit?.base_unit&&this.lot?1:null,this.texteQuantite=null===this.quantite?"":String(this.quantite)}saisirQuantite(e){this.texteQuantite=e;const t=Ve(e);if(!t.ok)return this.erreur="Quantité : ce n’est pas un nombre.",void(this.quantite=null);this.erreur=null,this.quantite=t.valeur}choisirRaccourci(e){this.erreur=null,this.quantite=e,this.texteQuantite=String(e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}async enregistrer(){if(this.enCours||!this.file||!this.lot||null===this.produit)return;if(null===this.quantite||!(this.quantite>0))return void(this.erreur="Quantité : donne un nombre supérieur à zéro.");const e=this.partage&&"consumption"===this.motif;if(e&&!(this.partsTotal>=1&&this.partsTotal<=24&&this.partsMoi>=0&&this.partsMoi<=this.partsTotal))return void(this.erreur=this.partsTotal>24?"On ne sert pas plus de 24 parts.":"On ne mange pas plus de parts qu’il n’en a été servi.");this.erreur=null,this.enCours=!0,this.enAttenteEnvoi=!1;const t={product_id:this.produit.id,quantity:this.quantite,reason:this.motif};this.quantite<=this.lot.remaining&&(t.batch_id=this.lot.id),e&&(t.parts_total=this.partsTotal,t.parts_mine=this.partsMoi);const i=this.file.ajouter("home_stock/stock/consume",t);this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile());const s=await i.sort;this.enCours=!1,"envoyee"===s?this.dispatchEvent(new CustomEvent("consommation-enregistree",{bubbles:!0,composed:!0})):"en-attente"===s&&(this.enAttenteEnvoi=!0)}rendreMotifs(){return I`
      <section class="motifs">
        ${Object.keys(Xe).map(e=>I`
          <button type="button" class="motif ${this.motif===e?"motif-actif":""}"
            @click=${()=>{this.motif=e}}>
            ${Xe[e]}
          </button>
        `)}
      </section>
    `}rendreParts(){return"consumption"!==this.motif?B:I`
      <section class="parts">
        <label class="partage-bascule">
          <input type="checkbox" .checked=${this.partage}
            @change=${e=>{this.partage=e.target.checked}} />
          Je partage
        </label>
        ${this.partage?I`
          <div class="compteurs">
            <label class="compteur">
              Parts servies
              <input class="parts-total" type="number" inputmode="numeric" min="1" max=${24}
                .value=${String(this.partsTotal)}
                @input=${e=>{const t=Number.parseInt(e.target.value,10);Number.isFinite(t)&&(this.partsTotal=t)}} />
            </label>
            <label class="compteur">
              Les miennes
              <input class="parts-moi" type="number" inputmode="numeric" min="0" max=${this.partsTotal}
                .value=${String(this.partsMoi)}
                @input=${e=>{const t=Number.parseInt(e.target.value,10);Number.isFinite(t)&&(this.partsMoi=t)}} />
            </label>
          </div>`:B}
      </section>
    `}consigneAffichee(){if(!this.emballage||!this.lot)return null;const e="waste"===this.motif||"expired"===this.motif,t=null!==this.quantite&&this.quantite>=this.lot.remaining;return e||t?function(e){const t=[];for(const i of e){const e=Ke[i];void 0===e||t.includes(e)||t.push(e)}return 0===t.length?null:t.map((e,t)=>0===t?e:e.toLowerCase()).join(" et ")}(this.emballage.bins):null}render(){if(!this.produit)return B;if(!this.lot)return I`
        <section class="entete">
          <h2 class="nom">${this.produit.name}</h2>
        </section>
        <p class="plus-rien">Plus rien en stock.</p>
      `;const e=function(e,t,i,s=null){if(e<=0)return[];const r=[];if("piece"===t)r.push({libelle:Ye(1,t),quantite:1});else if(null!==i&&i>0&&i<=e){const e="manual"===s?"Ma portion":"1 portion";r.push({libelle:`${e} (${Ye(i,t)})`,quantite:i})}"piece"!==t&&r.push({libelle:`La moitié (${Ye(e/2,t)})`,quantite:e/2}),r.push({libelle:`Tout le reste (${Ye(e,t)})`,quantite:e});const n=new Set;return r.filter(t=>t.quantite<=e&&!n.has(t.quantite)&&n.add(t.quantite))}(this.lot.remaining,this.produit.base_unit,this.portion,this.portionSource),t=this.consigneAffichee();return I`
      <section class="entete">
        <h2 class="nom">${this.produit.name}</h2>
        <p class="reste">
          Reste ${i=this.lot.remaining,s=this.produit.base_unit,"piece"===s?`${Oe(i)} pièce${i>=2?"s":""}`:`${Oe(i)} ${s}`} sur le lot visé
          ${this.lot.best_before?I` — DLC ${function(e){const t=/^(\d{4})-(\d{2})-(\d{2})$/.exec(e);return t?`${t[3]}/${t[2]}/${t[1]}`:e}(this.lot.best_before)}`:B}
        </p>
      </section>

      <section class="raccourcis">
        ${e.map(e=>I`
          <button type="button" class="raccourci" @click=${()=>this.choisirRaccourci(e.quantite)}>
            ${e.libelle}
          </button>
        `)}
      </section>

      ${t?I`<p class="tri">Emballage : ${t}</p>`:B}

      <label class="pave-label">
        Autre quantité
        <input class="pave" inputmode="decimal" .value=${this.texteQuantite}
          @input=${e=>this.saisirQuantite(e.target.value)} />
      </label>

      ${this.rendreMotifs()}
      ${this.rendreParts()}

      ${this.erreur?I`<p class="erreur">${this.erreur}</p>`:B}
      ${this.enAttenteEnvoi?I`
        <p class="en-attente">Pas encore envoyé — ça repartira dès que le réseau revient.</p>
      `:B}

      <button type="button" class="enregistrer" ?disabled=${this.enCours} @click=${this.enregistrer}>
        ${Xe[this.motif]}
      </button>
    `;var i,s}};et.styles=[we,a`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--hs-text); }
    .nom { margin: 0; font-size: 1.2rem; }
    .reste { margin: 2px 0; color: var(--hs-text-2); }
    .plus-rien { color: var(--hs-text-2); }
    .tri { margin: 4px 0; color: var(--hs-text); font-size: 0.95rem; }
    .raccourcis { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
    .raccourci {
      min-height: var(--hs-touch); min-width: var(--hs-touch); flex: 1 1 auto; font-size: 1rem; border-radius: 8px; border: none;
      background: var(--hs-accent); color: var(--hs-on-accent); padding: 4px 8px;
    }
    .pave-label { display: block; margin: 8px 0; }
    .pave { min-height: var(--hs-touch); font-size: 1rem; padding: 4px 8px; box-sizing: border-box; width: 100%; }
    .motifs { display: flex; gap: 8px; margin: 12px 0; }
    .motif {
      min-height: var(--hs-touch); flex: 1 1 auto; font-size: 1rem; border-radius: 8px; border: none;
      background: var(--hs-surface-2); color: var(--hs-text);
    }
    .motif-actif { background: var(--hs-accent); color: var(--hs-on-accent); }
    .parts { margin: 12px 0; padding: 8px; border-radius: 8px; background: var(--hs-surface-2); }
    .partage-bascule { display: flex; align-items: center; gap: 8px; min-height: var(--hs-touch); }
    .partage-bascule input { width: 22px; height: 22px; }
    .compteurs { display: flex; gap: 12px; margin-top: 8px; }
    .compteur { flex: 1 1 auto; display: block; }
    .parts-total, .parts-moi { min-height: var(--hs-touch); font-size: 1rem; padding: 4px 8px; box-sizing: border-box; width: 100%; }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .erreur, .en-attente {
      color: var(--hs-text); border-left: 3px solid var(--hs-danger);
      padding-left: 8px; font-size: 0.9rem;
    }
    .enregistrer {
      display: block; width: 100%; min-height: var(--hs-touch); font-size: 1.2rem; border-radius: 12px;
      border: none; background: var(--hs-accent); color: var(--hs-on-accent);
      margin-top: 12px;
    }
    .enregistrer:disabled { opacity: 0.5; }
  `],e([pe({attribute:!1})],et.prototype,"connexion",void 0),e([pe({attribute:!1})],et.prototype,"file",void 0),e([pe({type:Number})],et.prototype,"productId",void 0),e([de()],et.prototype,"produit",void 0),e([de()],et.prototype,"lot",void 0),e([de()],et.prototype,"portion",void 0),e([de()],et.prototype,"portionSource",void 0),e([de()],et.prototype,"emballage",void 0),e([de()],et.prototype,"quantite",void 0),e([de()],et.prototype,"motif",void 0),e([de()],et.prototype,"partage",void 0),e([de()],et.prototype,"partsTotal",void 0),e([de()],et.prototype,"partsMoi",void 0),e([de()],et.prototype,"erreur",void 0),e([de()],et.prototype,"enCours",void 0),e([de()],et.prototype,"enAttenteEnvoi",void 0),e([de()],et.prototype,"texteQuantite",void 0),et=e([ce("home-stock-consommation")],et);const tt={kcal:{nom:"Énergie",unite:"kcal"},proteins:{nom:"Protéines",unite:"g"},carbohydrates:{nom:"Glucides",unite:"g"},sugars:{nom:"Sucres",unite:"g"},added_sugars:{nom:"Sucres ajoutés",unite:"g"},fat:{nom:"Matières grasses",unite:"g"},saturated_fat:{nom:"Graisses saturées",unite:"g"},fiber:{nom:"Fibres",unite:"g"},salt:{nom:"Sel",unite:"g"}},it={day:14,week:12,month:12},st={day:"Jours",week:"Semaines",month:"Mois"};function rt(e){return`${e.toFixed(2).replace(".",",")} €`}let nt=class extends oe{constructor(){super(...arguments),this.large=!1,this.jour=null,this.serie=null,this.granularite="day",this.enCours=!1,this.seauSelectionne=null,this.detailOuvert=null,this.apercu=null,this.correctionArmee=null}connectedCallback(){super.connectedCallback(),this.chargerJour(),this.chargerSerie(this.granularite)}async chargerJour(e){this.connexion&&(this.jour=await this.connexion.appeler("home_stock/journal/day",e?{date:e}:{}))}async chargerSerie(e){if(this.connexion){this.enCours=!0;try{this.serie=await this.connexion.appeler("home_stock/journal/series",{granularity:e,count:it[e]})}finally{this.enCours=!1}}}async choisirGranularite(e){this.granularite=e,this.seauSelectionne=null,await this.chargerSerie(e)}async ouvrirSeau(e){"day"===this.granularite?(this.seauSelectionne=null,await this.chargerJour(e.label)):(this.jour=null,this.seauSelectionne=e)}partDeLaBarre(e,t){return t>0?e/t:0}rendreBarres(){const e=this.serie?.buckets??[],t=Math.max(0,...e.map(e=>e.kcal));return I`
      <div class="barres">
        ${e.map(e=>{const i=this.partDeLaBarre(e.kcal,t);return I`
            <button class="barre" data-part=${i}
                    style=${`--part: ${Math.round(100*i)}%`}
                    title=${`${e.label} — ${Math.round(e.kcal)} kcal`}
                    @click=${()=>this.ouvrirSeau(e)}>
              <span class="barre-remplissage"></span>
            </button>`})}
      </div>`}rendreGranularites(){return I`
      <nav class="granularites">
        ${Object.keys(st).map(e=>I`
          <button type="button" class="granularite ${this.granularite===e?"granularite-active":""}"
            @click=${()=>this.choisirGranularite(e)}>
            ${st[e]}
          </button>
        `)}
      </nav>
    `}rendreEntree(e){const t=null!==e.parts_total&&e.parts_total!==e.parts_mine,i=null!==(e.corrected_by??null),s=null!==(e.corrects_id??null),r=["entree","consumption"!==e.reason?"jete":"",i?"corrigee":"",s?"contrepassation":""].filter(Boolean).join(" ");return I`
      <li class=${r}>
        <button class="entree-ouvrir" @click=${()=>this.ouvrirDetail(e)}>
          <span class="entree-nom">${e.product_name}</span>
          <span class="entree-quantite">
            ${Oe(Math.abs(e.quantity))} ${e.base_unit}
          </span>
          ${t?I`
            <span class="entree-parts">${e.parts_mine??0}/${e.parts_total}</span>
          `:B}
          <span class="entree-kcal">${null===e.kcal?"—":`${Math.round(e.kcal)} kcal`}</span>
        </button>
        ${this.detailOuvert===e.id?this.rendreDetail():B}
      </li>
    `}async ouvrirDetail(e){if(this.detailOuvert!==e.id){if(this.detailOuvert=e.id,this.apercu=null,this.correctionArmee=null,this.connexion)try{this.apercu=await this.connexion.appeler("home_stock/movement/correction_preview",{movement_id:e.id})}catch{this.apercu=null}}else this.detailOuvert=null}ecrire(e,t){this.file&&(this.file.ajouter(e,t),this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0})),this.file.rejouer())}confirmerCorrection(){const e=this.correctionArmee;e&&("mouvement"===e.cible?this.ecrire("home_stock/movement/correct",{movement_id:e.id}):this.ecrire("home_stock/meal/correct",{meal_id:e.id}),this.correctionArmee=null,this.detailOuvert=null)}rendreDetail(){const e=this.apercu;if(!e)return I`<div class="detail"><p>Chargement…</p></div>`;const t=e.batch_entered_at?` et remet ${Oe(e.quantity)} ${e.base_unit??""} dans le lot du ${e.batch_entered_at.slice(0,10)}`:"",i=[null===e.kcal?null:`${Math.round(e.kcal)} kcal`,null===e.cost?null:rt(e.cost)].filter(Boolean).join(", ");return I`
      <div class="detail">
        <p class="annonce">${`Annule ${Oe(e.quantity)} ${e.base_unit??""} de ${e.product_name??""}`+(i?` — ${i}`:"")+t+"."}</p>
        ${e.refusal?I`<p class="refus">${e.refusal}</p>`:B}
        ${this.correctionArmee?I`
          <button class="confirmer-correction" @click=${this.confirmerCorrection}>
            Confirmer
          </button>
          <button class="annuler-correction"
            @click=${()=>{this.correctionArmee=null}}>Annuler</button>
        `:I`
          ${e.correctable?I`
            <button class="corriger" @click=${()=>{this.correctionArmee={cible:"mouvement",id:e.movement_id}}}>Corriger</button>
          `:B}
          ${!e.correctable&&e.meal_id?I`
            <button class="corriger-repas" @click=${()=>{this.correctionArmee={cible:"repas",id:e.meal_id}}}>Corriger le repas</button>
          `:B}
        `}
      </div>
    `}rendreJour(){const e=this.jour;return e?I`
      <section class="jour">
        <h2 class="titre-jour">${e.food_day}</h2>
        ${0===e.entries.length?I`
          <p class="vide">Rien de déclaré ce jour-là.</p>
        `:I`
          <ul class="entrees">
            ${e.entries.map(e=>this.rendreEntree(e))}
          </ul>
        `}
        <p class="total-kcal">${Math.round(e.totals.kcal)} kcal</p>
        <p class="total-cout">
          ${rt(e.totals.cost)}
          ${e.totals.waste_cost>0?I` — dont ${rt(e.totals.waste_cost)} jeté`:B}
        </p>
        ${e.totals.unvalued>0?I`
          <p class="non-chiffre">${e.totals.unvalued} sortie(s) sans calories connues.</p>
        `:B}
        ${this.rendreObjectifs(e)}
      </section>
    `:B}rendreObjectifs(e){const t=e.goals??{},i=e.week_mean??{},s=Object.keys(tt).filter(e=>"number"==typeof t[e]);return 0===s.length?B:I`
      <ul class="objectifs">
        ${s.map(s=>{const{nom:r,unite:n}=tt[s],a=t[s],o=e.totals[s]??0,l=i[s];return I`
            <li class="objectif ${o>a?"objectif-depasse":""}">
              ${r} ${Oe(o)} / ${Oe(a)} ${n}
            </li>
            ${"number"==typeof l&&l>a?I`
              <li class="objectif-semaine">
                ${r}, moyenne sur 7 jours ${Oe(l)} /
                ${Oe(a)} ${n}
              </li>
            `:B}
          `})}
      </ul>
    `}rendreSeauTotaux(){const e=this.seauSelectionne;return e?I`
      <section class="jour">
        <h2 class="titre-jour">${e.label}</h2>
        <p class="total-kcal">${Math.round(e.kcal)} kcal</p>
        <p class="total-cout">
          ${rt(e.cost)}
          ${e.waste_cost>0?I` — dont ${rt(e.waste_cost)} jeté`:B}
        </p>
      </section>
    `:B}rendrePeriode(){return"day"===this.granularite?this.rendreJour():this.rendreSeauTotaux()}render(){return this.large?I`
        <h1 class="titre">Journal</h1>
        ${this.rendreGranularites()}
        <div class="deux-colonnes">
          <div class="colonne-serie">${this.rendreBarres()}</div>
          <div class="colonne-detail">${this.rendrePeriode()}</div>
        </div>
      `:I`
      <h1 class="titre">Journal</h1>
      ${this.rendreGranularites()}
      ${this.rendreBarres()}
      ${this.rendrePeriode()}
    `}};function at(e){return e.normalize("NFD").replace(/[̀-ͯ]/g,"").replace(/œ/g,"oe").replace(/æ/g,"ae").toLowerCase()}nt.styles=[we,a`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--hs-text); }
    .titre { margin: 0 0 8px; font-size: 1.2rem; }
    .granularites { display: flex; gap: 8px; margin-bottom: 8px; }
    .granularite {
      flex: 1 1 auto; min-height: var(--hs-touch); border-radius: 8px; border: none; font-size: 0.9rem;
      background: var(--hs-surface-2); color: var(--hs-text);
    }
    .granularite-active { background: var(--hs-accent); color: var(--hs-on-accent); }
    .entree-ouvrir {
      display: flex; width: 100%; gap: 8px; align-items: baseline; min-height: var(--hs-touch);
      border: none; background: transparent; color: inherit; font: inherit;
      text-align: left; padding: 0;
    }
    .corrigee .entree-nom, .corrigee .entree-quantite { text-decoration: line-through; }
    .contrepassation { color: var(--hs-text-2); }
    .detail {
      margin: 4px 0 8px; padding: 8px; border-radius: 8px;
      background: var(--hs-surface-2);
    }
    .annonce { margin: 0 0 8px; }
    .refus { margin: 0 0 8px; color: var(--hs-text-2); font-size: 0.9rem; }
    .corriger, .corriger-repas, .confirmer-correction, .annuler-correction {
      display: block; width: 100%; min-height: var(--hs-touch); border-radius: 8px; border: none;
      margin-top: 8px; font-size: 1rem;
    }
    .corriger, .corriger-repas, .confirmer-correction {
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .annuler-correction {
      background: var(--hs-surface); color: var(--hs-text);
    }
    .objectifs { list-style: none; margin: 4px 0 0; padding: 0; }
    .objectif { font-size: 0.95rem; }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .objectif-depasse {
      color: var(--hs-text); border-left: 3px solid var(--hs-danger); padding-left: 8px;
    }
    .objectif-semaine { font-size: 0.9rem; color: var(--hs-text-2); }
    /* La cible tactile de .barre est fixe (colonne pleine hauteur ici,
       ligne pleine largeur sous 700 px) — jamais la grandeur du seau, qui ne
       viendrait qu'agrandir les gros jours et rétrécir les petits sous les
       62 px. Quatorze seaux sur 412 px ne tiennent pas en colonnes larges de
       62 px (14 x 62 > 372 px de contenu disponible) : sous 700 px, le
       graphe passe donc en liste de lignes empilées, chacune pleine largeur,
       où c'est la largeur du remplissage qui porte la valeur. */
    .barres {
      display: flex; gap: 4px; margin: 8px 0 16px;
      padding: 8px; border-radius: 8px; background: var(--hs-surface-2); box-sizing: border-box;
    }
    .barre {
      /* Cible tactile réelle, pas juste visuelle : min-width tient la
         colonne à 62 px. La vue dense élargit la colonne « série » (voir
         plus bas) pour que les quatorze tiennent sur une seule ligne — un
         flex-wrap essayé ici étalait les deux dernières barres orphelines
         sur toute la largeur de leur ligne (round de correction 1), un
         défaut pire que l'original et invisible du vérificateur. */
      flex: 1 1 auto; min-width: var(--hs-touch); height: 120px; min-height: var(--hs-touch); box-sizing: border-box;
      display: flex; align-items: flex-end; border: none; border-radius: 4px; background: transparent; padding: 0;
    }
    .barre-remplissage {
      display: block; width: 100%; height: var(--part); min-height: 4px;
      border-radius: 4px 4px 0 0; background: var(--hs-accent); pointer-events: none;
    }
    @media (max-width: 700px) {
      .barres { flex-direction: column; }
      .barre { flex: none; width: 100%; height: auto; min-height: var(--hs-touch); align-items: stretch; }
      .barre-remplissage { width: var(--part); height: 100%; min-width: 4px; min-height: 0; border-radius: 0 4px 4px 0; }
    }
    .jour { margin-top: 8px; }
    .titre-jour { margin: 0 0 8px; font-size: 1rem; color: var(--hs-text-2); }
    .entrees { list-style: none; margin: 0 0 8px; padding: 0; }
    .entree {
      display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-height: var(--hs-touch);
      padding: 8px 0; border-bottom: 1px solid var(--hs-divider);
    }
    .entree-nom { flex: 1 1 auto; }
    .entree-quantite, .entree-kcal { color: var(--hs-text-2); font-size: 0.85rem; }
    .entree-parts {
      font-size: 0.8rem; padding: 2px 6px; border-radius: 999px;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .entree.jete { color: var(--hs-text); border-left: 3px solid var(--hs-danger); padding-left: 8px; }
    .vide { color: var(--hs-text-2); }
    .total-kcal { margin: 4px 0 0; font-size: 1.1rem; font-weight: 600; }
    .total-cout { margin: 2px 0; color: var(--hs-text-2); }
    .non-chiffre {
      color: var(--hs-text); border-left: 3px solid var(--hs-danger); padding-left: 8px; font-size: 0.85rem;
    }

    /* --- la vue dense (lot 6), au-delà de 1000 px --------------------------
       Quatorze cibles à 62 px de cible tactile chacune, quel que soit ce
       qui est peint dedans, ça fait 868 px de plancher pour la colonne
       « série » — un partage 2:1 n'en donnait que ~800 à 1280 px, d'où le
       défaut que le vérificateur a signalé (round Task 6) et le flex-wrap
       essayé puis écarté (round de correction 1 : il étalait les barres
       orphelines de la dernière ligne sur toute sa largeur). La colonne
       « série » prend donc sa largeur naturelle (0 0 auto) — quatorze
       barres + gouttières — et la colonne « détail » absorbe tout le reste
       en restant élastique (1 1 0, min-width nulle pour ne jamais pousser
       la grille hors cadre). À 1280 px il reste ~330 px au détail, plus
       qu'un téléphone où il tient déjà ; à 1920 la question ne se pose
       plus. */
    .deux-colonnes { display: flex; gap: 16px; align-items: start; }
    .colonne-serie { flex: 0 0 auto; }
    .colonne-detail { flex: 1 1 0; min-width: 0; }
    .deux-colonnes .barres { margin-top: 0; }
    .deux-colonnes .jour { margin-top: 0; }
  `],e([pe({attribute:!1})],nt.prototype,"connexion",void 0),e([pe({type:Boolean})],nt.prototype,"large",void 0),e([de()],nt.prototype,"jour",void 0),e([de()],nt.prototype,"serie",void 0),e([de()],nt.prototype,"granularite",void 0),e([de()],nt.prototype,"enCours",void 0),e([de()],nt.prototype,"seauSelectionne",void 0),e([pe({attribute:!1})],nt.prototype,"file",void 0),e([de()],nt.prototype,"detailOuvert",void 0),e([de()],nt.prototype,"apercu",void 0),e([de()],nt.prototype,"correctionArmee",void 0),nt=e([ce("home-stock-journal")],nt);let ot=class extends oe{constructor(){super(...arguments),this.enAttente=!1,this.recettes=[],this.filtre="",this.fiches=null,this.chercheEnLigne=!1,this.message=""}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(!this.connexion)return;const e=await this.connexion.appeler("home_stock/recipes/list",{});this.recettes=e.recipes??[]}get recettesFiltrees(){if(!this.filtre.trim())return this.recettes;const e=at(this.filtre.trim());return this.recettes.filter(t=>at(t.name).includes(e))}ouvrir(e){this.dispatchEvent(new CustomEvent("recette-ouverte",{detail:{recipe_id:e.id},bubbles:!0,composed:!0}))}async chercherAilleurs(){if(this.connexion&&!this.enAttente){this.chercheEnLigne=!0,this.message="";try{const e=await this.connexion.appeler("home_stock/recipe/search_external",{query:this.filtre.trim()});this.fiches=e.hits??[],this.fiches.length||(this.message=!1===e.reachable?"La source de recettes est injoignable pour le moment.":"Aucune recette trouvée à la source.")}finally{this.chercheEnLigne=!1}}}async importer(e){if(!this.connexion)return;const t=await this.connexion.appeler("home_stock/recipe/import_external",{source_ref:e.source_ref});this.message=t.adapted?`« ${e.name} » a été importée et adaptée en français.`:`« ${e.name} » a été importée. Elle est en anglais : à relire.`,this.fiches=null,await this.charger()}async marquerRelue(e){this.file&&(this.file.ajouter("home_stock/recipe/update",{recipe_id:e.id,fields:{needs_review:0}}),this.recettes=this.recettes.map(t=>t.id===e.id?{...t,needs_review:0}:t))}rendreRecette(e){return I`
      <button class="recette" @click=${()=>this.ouvrir(e)}>
        <span class="recette-nom">${e.name}</span>
        <span class="badges">
          ${e.needs_review?I`<span class="badge relire">à relire</span>`:B}
          ${e.unmatched_count>0?I`<span class="badge manque">${e.unmatched_count} non apparié${e.unmatched_count>1?"s":""}</span>`:B}
        </span>
      </button>
    `}rendreFiche(e){return I`
      <button class="fiche" @click=${()=>this.importer(e)}>
        <span class="fiche-nom">${e.name}</span>
        <span class="fiche-meta">${[e.category,e.area].filter(Boolean).join(" · ")}</span>
      </button>
    `}render(){const e=this.recettesFiltrees;return I`
      <div class="entete">
        <input class="recherche" type="search" placeholder="Chercher une recette"
               .value=${this.filtre}
               @input=${e=>{this.filtre=e.target.value}} />
        <button class="ailleurs" ?disabled=${this.enAttente||this.chercheEnLigne}
                @click=${()=>this.chercherAilleurs()}>
          ${this.chercheEnLigne?"Recherche…":"Chercher ailleurs"}
        </button>
      </div>

      ${this.message?I`<p class="message">${this.message}</p>`:B}

      ${this.fiches?I`<section class="fiches">
            <h2>Trouvées à la source</h2>
            ${this.fiches.map(e=>this.rendreFiche(e))}
          </section>`:B}

      ${e.length?I`<section class="liste">
            ${e.map(e=>this.rendreRecette(e))}
          </section>`:I`<p class="vide">${this.filtre?"Aucune recette ne correspond.":"Aucune recette pour le moment."}</p>`}
    `}};function lt(e,t=0){const i=Math.max(0,e);return{restant:i,enMarche:i>0,termine:0===i,duree:i}}function ct(e,t){if(!e.enMarche)return e;const i=Math.max(0,e.restant-Math.max(0,t));return{...e,restant:i,enMarche:i>0,termine:0===i}}function ut(e){const t=Math.max(0,e);return{restant:t,enMarche:!1,termine:!1,duree:t}}ot.styles=[we,a`
    :host { display: block; padding: 12px; color: var(--hs-text); }
    .entete { display: flex; gap: 8px; margin-bottom: 12px; }
    .recherche {
      flex: 1; min-height: var(--hs-touch); padding: 0 12px; font-size: 1rem;
      border: 1px solid var(--hs-divider); border-radius: 8px;
      background: var(--hs-surface); color: var(--hs-text);
    }
    .ailleurs {
      min-height: var(--hs-touch); padding: 0 16px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--hs-divider);
      background: var(--hs-surface); color: var(--hs-text);
    }
    .ailleurs[disabled] { opacity: 0.5; cursor: default; }
    .message { margin: 8px 0; }
    .liste, .fiches { display: flex; flex-direction: column; gap: 8px; }
    h2 { font-size: 1rem; margin: 12px 0 4px; }
    .recette, .fiche {
      display: flex; justify-content: space-between; align-items: center;
      gap: 8px; min-height: var(--hs-touch); padding: 8px 12px; text-align: left;
      border: 1px solid var(--hs-divider); border-radius: 8px; cursor: pointer;
      background: var(--hs-surface); color: var(--hs-text);
      font-size: 1rem;
    }
    .recette-nom, .fiche-nom { flex: 1; }
    .badges { display: flex; gap: 6px; }
    .badge {
      padding: 2px 8px; border-radius: 999px; font-size: 0.8rem; white-space: nowrap;
    }
    /* --hs-on-warning est recalculé au montage : l'aplat reste lisible sur
       les trois palettes mesurées. */
    .relire { background: var(--hs-warning); color: var(--hs-on-warning); }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : --hs-danger se dit en bordure. */
    .manque {
      background: var(--hs-surface); color: var(--hs-text);
      border: 2px solid var(--hs-danger);
    }
    .fiche-meta { opacity: 0.75; font-size: 0.85rem; }
    .vide { opacity: 0.75; }
    @media (max-width: 700px) {
      .entete { flex-direction: column; }
    }
  `],e([pe({attribute:!1})],ot.prototype,"connexion",void 0),e([pe({attribute:!1})],ot.prototype,"file",void 0),e([pe({type:Boolean})],ot.prototype,"enAttente",void 0),e([de()],ot.prototype,"recettes",void 0),e([de()],ot.prototype,"filtre",void 0),e([de()],ot.prototype,"fiches",void 0),e([de()],ot.prototype,"chercheEnLigne",void 0),e([de()],ot.prototype,"message",void 0),ot=e([ce("home-stock-recettes")],ot);let ht=class extends oe{constructor(){super(...arguments),this.vue=null,this.page=0,this.ingredientsOuverts=!1,this.minuteurs={},this._wakeLock=null}connectedCallback(){super.connectedCallback(),this.charger(),this.garderEveille(),this._tic=setInterval(()=>this.avancerLesMinuteurs(),1e3)}disconnectedCallback(){super.disconnectedCallback(),this._tic&&clearInterval(this._tic),this.relacherEveil()}async charger(){this.connexion&&void 0!==this.recipeId&&(this.vue=await this.connexion.appeler("home_stock/recipe/get",{recipe_id:this.recipeId}))}async garderEveille(){const e=navigator?.wakeLock;if(e?.request)try{this._wakeLock=await e.request("screen")}catch{this._wakeLock=null}}async relacherEveil(){try{await(this._wakeLock?.release())}catch{}this._wakeLock=null}get nombreDePages(){return(this.vue?.steps.length??0)+1}get peutReculer(){return this.page>0}get peutAvancer(){return this.page<this.nombreDePages-1}reculer(){this.peutReculer&&(this.page-=1)}avancerPage(){this.peutAvancer&&(this.page+=1)}ouvrirIngredients(){this.ingredientsOuverts=!0}fermerIngredients(){this.ingredientsOuverts=!1}fermer(){this.dispatchEvent(new CustomEvent("recette-fermee",{bubbles:!0,composed:!0}))}validerRepas(){void 0!==this.mealId&&this.dispatchEvent(new CustomEvent("valider-repas",{detail:{meal_id:this.mealId},bubbles:!0,composed:!0}))}basculerMinuteur(e){if(null===e.timer_seconds)return;const t=this.minuteurs[e.id];this.minuteurs={...this.minuteurs,[e.id]:t&&(t.enMarche||t.termine)?ut(e.timer_seconds):lt(e.timer_seconds)}}avancerLesMinuteurs(){const e=Object.entries(this.minuteurs);e.some(([,e])=>e.enMarche)&&(this.minuteurs=Object.fromEntries(e.map(([e,t])=>[e,ct(t,1)])))}libelleQuantite(e){return e.display_amount?e.display_amount:null===e.amount?"":Te(e.amount,e.product_base_unit??"g",e.measure_name,e.packaging_name)}async apparier(e,t){if(this.file&&(this.file.ajouter("home_stock/recipe/ingredient/match",{ingredient_id:e.id,product_id:t,state:"confirmed",create_alias:!0}),this.file.rejouer?.(),this.vue)){const i=e.candidates?.find(e=>e.product_id===t)?.name??null;this.vue={...this.vue,ingredients:this.vue.ingredients.map(s=>s.id===e.id?{...s,match_state:"confirmed",product_id:t,product_name:i,candidates:[]}:s)}}}rendreIngredients(){const e=this.vue?.ingredients??[];return I`
      <section class="ingredients">
        <h2>Ingrédients</h2>
        <ul>
          ${e.map(e=>I`
            <li class="ingredient ${"unmatched"===e.match_state?"a-la-main":""}">
              <span class="quantite">${this.libelleQuantite(e)}</span>
              <span class="ingredient-nom">${e.product_name??e.raw_text}</span>
              ${"unmatched"===e.match_state?I`<span class="mention">à sortir à la main</span>`:B}
              ${"unmatched"===e.match_state&&e.candidates?.length?I`<span class="candidats">
                    ${e.candidates.map(t=>I`
                      <button class="candidat"
                              @click=${()=>this.apparier(e,t.product_id)}>
                        ${t.name}
                      </button>`)}
                  </span>`:B}
            </li>`)}
        </ul>
        <button class="fermer-ingredients" @click=${()=>this.fermerIngredients()}>
          Revenir à la recette
        </button>
      </section>
    `}rendreCouverture(){const e=this.vue.recipe;return I`
      <section class="couverture">
        ${e.image_url?I`<img class="image" src=${e.image_url} alt="" />`:B}
        <h1>${e.name}</h1>
        <p class="meta">
          ${e.total_minutes?I`<span class="duree">⏱ ${e.total_minutes} min</span>`:B}
          <span class="parts">🔥 ${e.servings} part${e.servings>1?"s":""}</span>
          ${e.utensils?I`<span class="ustensiles">🍳 ${e.utensils}</span>`:B}
        </p>
        ${e.summary?I`<p class="accroche">${e.summary}</p>`:B}
      </section>
    `}rendrePuce(e){const t=this.minuteurs[e.id];return I`
      <li class="puce">
        <span class="puce-texte">${e.text}</span>
        ${null!==e.timer_label&&null!==e.timer_seconds?I`<button class="minuteur ${t?.termine?"termine":""}"
                         @click=${()=>this.basculerMinuteur(e)}>
              ${e.timer_label} ·
              ${function(e){const t=Math.max(0,Math.round(e)),i=Math.floor(t/3600),s=Math.floor(t%3600/60),r=t%60,n=e=>String(e).padStart(2,"0");return i>0?`${i}:${n(s)}:${n(r)}`:`${s}:${n(r)}`}(t?t.restant:e.timer_seconds)}
            </button>`:B}
      </li>
    `}rendreEtape(e){return I`
      <section class="etape">
        ${e.image_url?I`<img class="image" src=${e.image_url} alt="" />`:B}
        <h2>${e.title??`Étape ${e.position}`}</h2>
        <ol class="puces">${e.instructions.map(e=>this.rendrePuce(e))}</ol>
      </section>
    `}render(){if(!this.vue)return I`<p class="chargement">Chargement…</p>`;if(this.ingredientsOuverts)return this.rendreIngredients();const e=!this.peutAvancer;return I`
      ${0===this.page?this.rendreCouverture():this.rendreEtape(this.vue.steps[this.page-1])}

      <nav class="barre">
        <button class="precedent" ?disabled=${!this.peutReculer}
                @click=${()=>this.reculer()}>Précédent</button>
        <button class="ingredients-bouton" @click=${()=>this.ouvrirIngredients()}>
          Ingrédients
        </button>
        <span class="position">${this.page+1} / ${this.nombreDePages}</span>
        ${e&&void 0!==this.mealId?I`<button class="cuisine" @click=${()=>this.validerRepas()}>
              J'ai cuisiné
            </button>`:I`<button class="suivant" ?disabled=${!this.peutAvancer}
                         @click=${()=>this.avancerPage()}>Suivant</button>`}
      </nav>
    `}};ht.styles=[we,a`
    :host {
      display: block; padding: 16px; font-size: 1.25rem;
      color: var(--hs-text);
    }
    .image { width: 100%; max-height: 40vh; object-fit: cover; border-radius: 12px; }
    h1 { font-size: 1.8rem; margin: 12px 0 4px; }
    h2 { font-size: 1.5rem; margin: 12px 0 8px; }
    .meta { display: flex; flex-wrap: wrap; gap: 12px; opacity: 0.85; margin: 4px 0; }
    .accroche { opacity: 0.9; }
    .puces { display: flex; flex-direction: column; gap: 12px; padding-left: 1.2em; }
    .puce { line-height: 1.5; }
    .minuteur {
      display: block; margin-top: 8px; min-height: var(--hs-touch); padding: 0 16px;
      font-size: 1.1rem; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--hs-divider);
      background: var(--hs-surface); color: var(--hs-text);
    }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .minuteur.termine { background: var(--hs-surface); color: var(--hs-text); border: 2px solid var(--hs-danger); }
    .ingredients ul { list-style: none; padding: 0; display: flex;
                      flex-direction: column; gap: 12px; }
    .ingredient { display: flex; flex-wrap: wrap; gap: 10px;
                  align-items: baseline; min-height: var(--hs-touch); }
    .quantite { font-weight: 600; min-width: 6em; }
    .a-la-main .mention { opacity: 0.8; font-size: 0.9rem; font-style: italic; }
    .candidats { display: flex; flex-wrap: wrap; gap: 6px; width: 100%; }
    .candidat {
      min-height: var(--hs-touch); padding: 0 12px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--hs-divider); font-size: 0.95rem;
      background: var(--hs-surface); color: var(--hs-text);
    }
    .barre {
      display: flex; gap: 8px; align-items: center; margin-top: 20px;
      position: sticky; bottom: 0; padding: 8px 0;
      background: var(--hs-surface);
    }
    .barre button, .fermer-ingredients {
      min-height: var(--hs-touch); padding: 0 16px; font-size: 1rem; border-radius: 8px;
      cursor: pointer; border: 1px solid var(--hs-divider);
      background: var(--hs-surface); color: var(--hs-text);
    }
    .barre button[disabled] { opacity: 0.4; cursor: default; }
    .position { margin-left: auto; opacity: 0.75; }
    .cuisine { background: var(--hs-accent); color: var(--hs-on-accent); }
    @media (max-width: 700px) {
      :host { font-size: 1.15rem; }
      .quantite { min-width: 4.5em; }
    }
  `],e([pe({attribute:!1})],ht.prototype,"connexion",void 0),e([pe({attribute:!1})],ht.prototype,"file",void 0),e([pe({type:Number})],ht.prototype,"recipeId",void 0),e([pe({type:Number})],ht.prototype,"mealId",void 0),e([de()],ht.prototype,"vue",void 0),e([de()],ht.prototype,"page",void 0),e([de()],ht.prototype,"ingredientsOuverts",void 0),e([de()],ht.prototype,"minuteurs",void 0),ht=e([ce("home-stock-recette")],ht);const pt={ok:"prêt",short:"stock insuffisant",unmatched:"produit non identifié",unquantified:"quantité inconnue",ignored:"ignoré"};let dt=class extends oe{constructor(){super(...arguments),this.preview=null,this.partsMangees=1,this.partage=!1,this.partsTotal=4,this.partsMoi=1,this.retirees=[],this.arme=!1,this.enCours=!1,this.enAttenteEnvoi=!1,this.erreur=null}connectedCallback(){super.connectedCallback(),this.simuler()}async simuler(){this.connexion&&void 0!==this.mealId&&(this.preview=await this.connexion.appeler("home_stock/meal/preview",{meal_id:this.mealId,skip_ingredient_ids:this.retirees}))}async retirerLigne(e){this.retirees=[...this.retirees,e.ingredient_id],this.arme=!1,await this.simuler()}get bloque(){return(this.preview?.blocking.length??0)>0}valider(){this.bloque||this.enCours||(this.arme?this.envoyer():this.arme=!0)}annuler(){this.arme=!1}async envoyer(){if(!this.file||void 0===this.mealId||this.enCours)return;const e=this.partsMangees;if(null===e||e<0)return void(this.erreur="Parts mangées : donne un nombre positif ou zéro.");if(this.preview?.dish&&e>this.preview.dish.parts)return void(this.erreur="On ne mange pas plus de parts que le plat n’en fait.");if(this.partage&&!(this.partsTotal>=1&&this.partsTotal<=24&&this.partsMoi>=0&&this.partsMoi<=this.partsTotal))return void(this.erreur=this.partsTotal>24?"On ne sert pas plus de 24 parts.":"On ne mange pas plus de parts qu’il n’en a été servi.");this.erreur=null,this.enCours=!0,this.arme=!1;const t={meal_id:this.mealId,portions_eaten:e,skip_ingredient_ids:this.retirees};this.partage&&(t.parts_total=this.partsTotal,t.parts_mine=this.partsMoi);const i=this.file.ajouter("home_stock/meal/validate",t);this.file.rejouer?.();const s=await i.sort;this.enCours=!1,this.enAttenteEnvoi="en-attente"===s,"refusee"!==s?this.dispatchEvent(new CustomEvent("repas-valide",{detail:{meal_id:this.mealId},bubbles:!0,composed:!0})):this.erreur="La validation a été refusée."}rendreLigne(e,t){return I`
      <li class="ligne statut-${e.status}">
        <span class="ligne-quantite">${e.label}</span>
        <span class="ligne-nom">${e.product_name??e.raw_text}</span>
        <span class="ligne-statut">${pt[e.status]}</span>
        ${t?I`<button class="retirer" @click=${()=>this.retirerLigne(e)}>
              Retirer
            </button>`:B}
      </li>
    `}rendreValeur(e,t=""){return"number"!=typeof e?"—":`${Oe(e)}${t}`}rendrePlat(){const e=this.preview?.dish;return e?I`
      <section class="plat">
        <h2>${e.product_name}</h2>
        <dl>
          <div><dt>Parts</dt><dd class="plat-parts">${Oe(e.parts)}</dd></div>
          <div><dt>À consommer avant</dt>
               <dd class="plat-dlc">${e.best_before}</dd></div>
          <div><dt>Coût</dt>
               <dd class="plat-cout">${this.rendreValeur(e.cost," €")}</dd></div>
          <div><dt>Par part</dt>
               <dd class="plat-kcal">${this.rendreValeur(e.kcal," kcal")}</dd></div>
        </dl>
      </section>
    `:B}rendreParts(){return I`
      <section class="parts">
        <label class="partage-bascule">
          <input type="checkbox" .checked=${this.partage}
            @change=${e=>{this.partage=e.target.checked}} />
          Je partage
        </label>
        ${this.partage?I`
          <div class="compteurs">
            <label class="compteur">
              Parts servies
              <input class="parts-total" type="number" inputmode="numeric"
                min="1" max=${24} .value=${String(this.partsTotal)}
                @input=${e=>{const t=Number.parseInt(e.target.value,10);Number.isFinite(t)&&(this.partsTotal=t)}} />
            </label>
            <label class="compteur">
              Les miennes
              <input class="parts-moi" type="number" inputmode="numeric"
                min="0" max=${this.partsTotal} .value=${String(this.partsMoi)}
                @input=${e=>{const t=Number.parseInt(e.target.value,10);Number.isFinite(t)&&(this.partsMoi=t)}} />
            </label>
          </div>`:B}
      </section>
    `}render(){if(!this.preview)return I`<p class="chargement">Chargement…</p>`;const e=this.preview;return I`
      <h1>${e.recipe?.name??"Repas"}</h1>

      <section class="sorties">
        <h2>Ce qui sort du stock</h2>
        <ul>${e.lines.map(e=>this.rendreLigne(e,!0))}</ul>
      </section>

      ${e.by_hand.length?I`<section class="a-la-main">
            <h2>À sortir à la main</h2>
            <ul>${e.by_hand.map(e=>this.rendreLigne(e,!1))}</ul>
          </section>`:B}

      ${this.rendrePlat()}

      <label class="mangees">
        Parts mangées
        <input class="parts-mangees" type="text" inputmode="decimal"
          .value=${null===this.partsMangees?"":Oe(this.partsMangees)}
          @input=${e=>{const t=Ve(e.target.value);t.ok&&(this.partsMangees=t.valeur)}} />
      </label>

      ${this.rendreParts()}

      ${this.bloque?I`<p class="blocage">
            Il manque du stock pour au moins un ingrédient : ajustez la quantité
            ou retirez ces lignes avant de valider.
          </p>`:B}

      ${this.erreur?I`<p class="erreur">${this.erreur}</p>`:B}
      ${this.enAttenteEnvoi?I`<p class="en-attente">Enregistré, en attente de réseau.</p>`:B}

      ${this.arme?I`<p class="sans-retour">
            Cette validation ne s'annule pas : les mouvements écrits restent au
            journal.
          </p>`:B}

      <div class="actions">
        <button class="valider" ?disabled=${this.bloque||this.enCours}
                @click=${()=>this.valider()}>
          ${this.arme?"Confirmer la validation":"Valider le repas"}
        </button>
        ${this.arme?I`<button class="annuler" @click=${()=>this.annuler()}>Annuler</button>`:B}
      </div>
    `}};dt.styles=[we,a`
    :host { display: block; padding: 12px; color: var(--hs-text); }
    h1 { font-size: 1.4rem; margin: 0 0 12px; }
    h2 { font-size: 1.05rem; margin: 16px 0 6px; }
    ul { list-style: none; padding: 0; display: flex; flex-direction: column; gap: 6px; }
    .ligne {
      display: flex; align-items: center; gap: 10px; min-height: var(--hs-touch);
      padding: 4px 8px; border-radius: 8px;
      border: 1px solid var(--hs-divider);
    }
    .ligne-quantite { font-weight: 600; min-width: 6em; }
    .ligne-nom { flex: 1; }
    .ligne-statut { opacity: 0.75; font-size: 0.85rem; }
    .statut-short { border-color: var(--hs-danger); }
    .retirer, .valider, .annuler {
      min-height: var(--hs-touch); padding: 0 16px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--hs-divider); font-size: 1rem;
      background: var(--hs-surface); color: var(--hs-text);
    }
    .valider { background: var(--hs-accent); color: var(--hs-on-accent); }
    .valider[disabled] { opacity: 0.4; cursor: default; }
    .plat dl { display: flex; flex-wrap: wrap; gap: 12px; margin: 0; }
    .plat dt { opacity: 0.75; font-size: 0.85rem; }
    .plat dd { margin: 0; font-weight: 600; }
    .mangees { display: flex; flex-direction: column; gap: 4px; margin-top: 16px; }
    .parts-mangees { min-height: var(--hs-touch); font-size: 1rem; padding: 4px 8px;
                     box-sizing: border-box; }
    .partage-bascule { display: flex; align-items: center; gap: 8px; min-height: var(--hs-touch); }
    .partage-bascule input { width: 22px; height: 22px; }
    .compteurs { display: flex; gap: 12px; }
    .parts-total, .parts-moi { min-height: var(--hs-touch); font-size: 1rem; padding: 4px 8px;
                               box-sizing: border-box; width: 100%; }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .blocage, .erreur { color: var(--hs-text); border-left: 3px solid var(--hs-danger); padding-left: 8px; }
    .sans-retour { font-weight: 600; }
    .actions { display: flex; gap: 8px; margin-top: 16px; }
    @media (max-width: 700px) {
      .ligne { flex-wrap: wrap; }
      .compteurs { flex-direction: column; }
    }
  `],e([pe({attribute:!1})],dt.prototype,"connexion",void 0),e([pe({attribute:!1})],dt.prototype,"file",void 0),e([pe({type:Number})],dt.prototype,"mealId",void 0),e([de()],dt.prototype,"preview",void 0),e([de()],dt.prototype,"partsMangees",void 0),e([de()],dt.prototype,"partage",void 0),e([de()],dt.prototype,"partsTotal",void 0),e([de()],dt.prototype,"partsMoi",void 0),e([de()],dt.prototype,"retirees",void 0),e([de()],dt.prototype,"arme",void 0),e([de()],dt.prototype,"enCours",void 0),e([de()],dt.prototype,"enAttenteEnvoi",void 0),e([de()],dt.prototype,"erreur",void 0),dt=e([ce("home-stock-validation")],dt);const mt=[["breakfast","Petit-déjeuner"],["lunch","Déjeuner"],["dinner","Dîner"],["snack","En-cas"]],gt=["dimanche","lundi","mardi","mercredi","jeudi","vendredi","samedi"];function vt(e,t){const i=new Date(`${e}T12:00:00Z`);return i.setUTCDate(i.getUTCDate()+t),i.toISOString().slice(0,10)}function bt(e){const t=new Date(`${e}T12:00:00Z`);return`${gt[t.getUTCDay()]} ${t.getUTCDate()}`}let ft=class extends oe{constructor(){super(...arguments),this.large=!1,this.debut=(new Date).toISOString().slice(0,10),this.repas=[],this.manquants=[],this.armeAnnulation=null,this.message=null}connectedCallback(){super.connectedCallback(),this.charger()}get jours(){const e=this.large?7:1;return Array.from({length:e},(e,t)=>vt(this.debut,t))}async charger(){if(!this.connexion)return;const e=this.jours,t=await this.connexion.appeler("home_stock/meals/list",{start:e[0],end:e[e.length-1]});this.repas=t.meals??[]}async allerA(e){this.debut=vt(this.debut,this.large?7*e:e),this.armeAnnulation=null,await this.charger()}repasDe(e,t){return this.repas.filter(i=>i.day===e&&i.slot_key===t).sort((e,t)=>e.position-t.position)}async poser(e,t){this.file&&(this.file.ajouter("home_stock/meal/plan",{day:e,slot_key:t,note:"Repas",servings:1}),this.file.rejouer?.(),await this.charger())}async deplacer(e,t,i){this.file&&("done"!==e.state?(this.message=null,this.file.ajouter("home_stock/meal/move",{meal_id:e.id,day:t,slot_key:i}),this.file.rejouer?.(),await this.charger()):this.message="Un repas validé ne se déplace pas : ses mouvements portent une date figée.")}async annuler(e){this.armeAnnulation===e.id?this.file&&(this.armeAnnulation=null,this.file.ajouter("home_stock/meal/cancel",{meal_id:e.id}),this.file.rejouer?.(),await this.charger()):this.armeAnnulation=e.id}ouvrirRecette(e){null!==e.recipe_id&&this.dispatchEvent(new CustomEvent("recette-ouverte",{detail:{recipe_id:e.recipe_id,meal_id:e.id},bubbles:!0,composed:!0}))}ouvrirValidation(e){"done"!==e.state&&this.dispatchEvent(new CustomEvent("valider-repas",{detail:{meal_id:e.id},bubbles:!0,composed:!0}))}nomDe(e){return e.recipe_name??e.product_name??e.note??"Repas"}rendreRepas(e){return I`
      <div class="repas etat-${e.state}">
        <button class="repas-nom" @click=${()=>this.ouvrirRecette(e)}>
          ${this.nomDe(e)}
        </button>
        ${"done"===e.state?I`<span class="valide">validé</span>`:I`
            <button class="valider-repas" @click=${()=>this.ouvrirValidation(e)}>
              Valider
            </button>
            <button class="annuler-repas" @click=${()=>this.annuler(e)}>
              ${this.armeAnnulation===e.id?"Confirmer":"Annuler"}
            </button>`}
      </div>
    `}rendreCase(e,t){const i=this.repasDe(e,t);return I`
      <div class="case">
        ${i.map(e=>this.rendreRepas(e))}
        <button class="poser" @click=${()=>this.poser(e,t)}>+</button>
      </div>
    `}render(){const e=this.jours;return I`
      <div class="entete">
        <button class="precedent-jour" @click=${()=>this.allerA(-1)}>Précédent</button>
        <span class="periode">${this.large?`${bt(e[0])} — ${bt(e[e.length-1])}`:bt(e[0])}</span>
        <button class="suivant-jour" @click=${()=>this.allerA(1)}>Suivant</button>
      </div>

      ${this.message?I`<p class="message">${this.message}</p>`:B}
      ${this.manquants.length?I`<p class="manquants">${this.manquants.length} produit${this.manquants.length>1?"s":""} à acheter</p>`:B}

      <div class="grille ${this.large?"large":"etroit"}">
        ${this.large?I`<div class="ligne-jours">
              <span class="coin"></span>
              ${e.map(e=>I`<span class="jour">${bt(e)}</span>`)}
            </div>`:B}
        ${mt.map(([t,i])=>I`
          <div class="ligne-creneau">
            <span class="creneau">${i}</span>
            ${e.map(e=>this.rendreCase(e,t))}
          </div>`)}
      </div>
    `}};ft.styles=[we,a`
    :host { display: block; padding: 12px; color: var(--hs-text); }
    .entete { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
    .periode { flex: 1; text-align: center; font-weight: 600; }
    .entete button, .poser, .repas-nom, .valider-repas, .annuler-repas {
      min-height: var(--hs-touch); padding: 0 12px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--hs-divider); font-size: 1rem;
      background: var(--hs-surface); color: var(--hs-text);
    }
    .grille { display: flex; flex-direction: column; gap: 8px; }
    .ligne-jours, .ligne-creneau { display: flex; gap: 8px; align-items: stretch; }
    .creneau, .coin { flex: 0 0 7em; display: flex; align-items: center;
                      font-weight: 600; }
    .jour { flex: 1; text-align: center; font-weight: 600; }
    .case {
      /* Zone de dépôt, pas une cible tactile : 48px reste volontairement en dur. */
      flex: 1; display: flex; flex-direction: column; gap: 6px; padding: 6px;
      border: 1px dashed var(--hs-divider); border-radius: 8px;
      min-height: 48px;
    }
    .repas { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
    .repas-nom { flex: 1; text-align: left; }
    .etat-done .repas-nom { text-decoration: line-through; opacity: 0.7; }
    .valide { opacity: 0.75; font-size: 0.85rem; }
    .poser { align-self: stretch; }
    .message, .manquants { margin: 4px 0; }
    .etroit .creneau { flex: 0 0 6em; }
    @media (max-width: 700px) {
      .creneau, .coin { flex: 0 0 5.5em; }
      .repas { flex-direction: column; align-items: stretch; }
    }
  `],e([pe({attribute:!1})],ft.prototype,"connexion",void 0),e([pe({attribute:!1})],ft.prototype,"file",void 0),e([pe({type:Boolean})],ft.prototype,"large",void 0),e([pe({type:String})],ft.prototype,"debut",void 0),e([de()],ft.prototype,"repas",void 0),e([de()],ft.prototype,"manquants",void 0),e([de()],ft.prototype,"armeAnnulation",void 0),e([de()],ft.prototype,"message",void 0),ft=e([ce("home-stock-planning")],ft);const xt={install:"posée",charge:"rechargée",replacement:"changée",removal:"retirée"};function $t(e){return e.orphaned?"entité introuvable":null===e.last_percent?"jamais relevée":"unavailable"===e.state||"unknown"===e.state?`${Math.trunc(e.last_percent)} % — muette depuis le dernier relevé`:`${Math.trunc(e.last_percent)} %`}function yt(e){if(!e.spare_label)return null;const t="built_in"!==e.kind,i=e.spare_in_stock??0,s=i>0?`${Number.isInteger(i)?i:i.toFixed(1)} en stock`:(t?"aucune":"aucun")+" en stock";return`${e.cell_count}× ${e.spare_label}, ${s}`}let _t=class extends oe{constructor(){super(...arguments),this.large=!1,this.piles=[],this.aDeclarer=[],this.selection=null,this.evenements=[],this.armee=null,this.refus=null,this.ignoree=null,this.motif="",this.erreurMotif=null}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(!this.connexion)return;const[e,t]=await Promise.all([this.connexion.appeler("home_stock/batteries/list"),this.connexion.appeler("home_stock/batteries/discover")]);this.piles=[...e.batteries].sort((e,t)=>(e.last_percent??Number.POSITIVE_INFINITY)-(t.last_percent??Number.POSITIVE_INFINITY)||e.label.localeCompare(t.label)),this.aDeclarer=t.sensors}async ecrire(e,t){if(!this.file)return;const i=this.file.ajouter(e,t);return this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0})),this.file.rejouer().then(()=>{this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}),i.reponse}async ouvrir(e){if(this.selection=e.id,this.armee=null,this.refus=null,this.evenements=[],!this.connexion)return;const t=await this.connexion.appeler("home_stock/battery/events",{battery_id:e.id});this.evenements=t.events}async surEvenement(e){const t="built_in"===e.kind||"rechargeable_cell"===e.kind?"charge":"replacement",i=`${e.id}:${t}`;if(this.armee!==i)return void(this.armee=i);this.armee=null;const s=await this.ecrire("home_stock/battery/event",{battery_id:e.id,kind:t});this.refus=s?.spare_refused??null,await this.charger()}async suivre(e){await this.ecrire("home_stock/battery/declare",{label:e.device_name||e.entity_id,kind:"primary",entity_registry_id:e.entity_registry_id,device_id:e.device_id,tracked:!0}),await this.charger()}async confirmerIgnorer(){const e=this.ignoree;e&&(this.motif.trim()?(this.erreurMotif=null,await this.ecrire("home_stock/battery/declare",{label:e.device_name||e.entity_id,kind:"primary",entity_registry_id:e.entity_registry_id,device_id:e.device_id,tracked:!1,exclusion_reason:this.motif.trim()}),this.ignoree=null,this.motif="",await this.charger()):this.erreurMotif="Un motif est nécessaire pour ignorer une pile.")}rendreADeclarer(){return 0===this.aDeclarer.length?B:I`
      <section class="section">
        <h2>${this.aDeclarer.length} pile(s) à déclarer</h2>
        ${this.aDeclarer.map(e=>I`
          <div class="capteur">
            <span class="libelle">${e.device_name??e.entity_id}</span>
            <span class="detail">${e.entity_id}${e.model?` — ${e.model}`:""}</span>
            <span class="detail">${null!==e.state?`${e.state} %`:"sans relevé"}</span>
          </div>
          <button class="action suivre" @click=${()=>this.suivre(e)}>Suivre</button>
          <button class="action ignorer" @click=${()=>{this.ignoree=e,this.erreurMotif=null}}>Ignorer</button>
        `)}
        ${this.ignoree?I`
          <label class="detail" for="motif">Motif — pourquoi cette pile n’est pas suivie</label>
          <input id="motif" class="motif" .value=${this.motif}
            @input=${e=>{this.motif=e.target.value}}>
          ${this.erreurMotif?I`<p class="erreur">${this.erreurMotif}</p>`:B}
          <button class="action confirmer-ignorer" @click=${()=>this.confirmerIgnorer()}>
            Confirmer et ignorer
          </button>
        `:B}
      </section>
    `}rendreFiche(e){const t="built_in"===e.kind||"rechargeable_cell"===e.kind?"charge":"replacement",i=this.armee===`${e.id}:${t}`,s="charge"===t?"de la recharger":"de la changer";return I`
      <section class="section">
        <h2>${e.label}</h2>
        <span class="detail">${e.verb} — ${$t(e)}</span>
        ${yt(e)?I`<span class="detail">${yt(e)}</span>`:B}
        <span class="detail">Seuils : ${e.low_percent} % / ${e.keep_percent} %</span>
        ${e.entity_id?I`<span class="detail">${e.entity_id}</span>`:B}
        <button class="action evenement" @click=${()=>this.surEvenement(e)}>
          ${i?`Confirmer : je viens ${s}`:`Je viens ${s}`}
        </button>
        ${this.refus?I`<p class="refus">${this.refus}</p>`:B}
        <h2>Historique</h2>
        ${0===this.evenements.length?I`<span class="detail">Aucun événement enregistré.</span>`:this.evenements.map(e=>I`
              <span class="evenement-passe">
                ${function(e){const t=new Date(e);if(Number.isNaN(t.getTime()))return e;const i=e=>String(e).padStart(2,"0");return`${i(t.getDate())}/${i(t.getMonth()+1)}/${t.getFullYear()}`}(e.occurred_at)} — ${xt[e.kind]??e.kind}
              </span>`)}
        <button class="action" @click=${()=>{this.selection=null,this.refus=null}}>
          Retour à la liste
        </button>
      </section>
    `}rendreTableau(){return I`
      ${this.rendreADeclarer()}
      <section class="section">
        <h2>${this.piles.length} pile(s) suivie(s)</h2>
        <table class="tableau">
          <thead>
            <tr><th>Pile</th><th>À faire</th><th>Niveau</th><th>Rechange</th></tr>
          </thead>
          <tbody>
            ${this.piles.map(e=>I`
              <tr class="ligne">
                <td class="libelle">
                  <button class="pile ouvrir" @click=${()=>this.ouvrir(e)}>${e.label}</button>
                </td>
                <td class="verbe">${e.verb}</td>
                <td class="detail">${$t(e)}</td>
                <td class="detail">${yt(e)??"—"}</td>
              </tr>
            `)}
          </tbody>
        </table>
      </section>
    `}render(){const e=this.piles.find(e=>e.id===this.selection)??null;return e?this.rendreFiche(e):this.large?this.rendreTableau():I`
      ${this.rendreADeclarer()}
      <section class="section">
        <h2>${this.piles.length} pile(s) suivie(s)</h2>
        ${this.piles.map(e=>I`
          <button class="pile" @click=${()=>this.ouvrir(e)}>
            <span class="libelle">${e.label}</span>
            <span class="verbe">${e.verb}</span>
            <span class="detail">${$t(e)}</span>
            ${yt(e)?I`<span class="detail">${yt(e)}</span>`:B}
          </button>
        `)}
      </section>
    `}};_t.styles=[we,a`
    :host { display: block; padding: 12px; color: var(--hs-text); box-sizing: border-box; }
    * { box-sizing: border-box; max-width: 100%; }
    /* Un entity_id est long et sans espace (sensor.browser_mod_606bfd06_
       browser_battery) : sans coupure, il pousse la page au-delà des 412 px
       de la dalle du téléphone, et le vérificateur de rendu le refuse — à
       juste titre. Pas de backtick dans ce commentaire : il est DANS un
       littéral de gabarit, et il le terminerait. */
    .libelle, .detail, .verbe, .lien { overflow-wrap: anywhere; }
    h2 { font-size: 1rem; margin: 12px 0 8px; }
    .pile, .capteur {
      display: block; width: 100%; min-height: var(--hs-touch); text-align: left;
      margin-bottom: 8px; padding: 10px 12px; border: none; border-radius: 8px;
      background: var(--hs-surface-2); color: var(--hs-text);
      font-size: 0.95rem;
    }
    .libelle { display: block; font-weight: 600; }
    .detail { display: block; font-size: 0.85rem; }
    .verbe { display: block; font-size: 0.85rem; }
    button.action {
      min-height: var(--hs-touch); width: 100%; border-radius: 8px; border: none;
      margin-bottom: 8px; font-size: 0.95rem;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    button.ignorer { background: var(--hs-surface-2); color: var(--hs-text); }
    .motif { width: 100%; min-height: var(--hs-touch); font-size: 1rem; box-sizing: border-box; }
    .refus, .erreur { margin: 8px 0; font-size: 0.9rem; }
    .evenement-passe { display: block; font-size: 0.85rem; margin-bottom: 4px; }

    /* --- la vue dense (lot 6), au-delà de 1000 px -------------------------
       Les classes de libellé, de détail et de verbe sont des blocs en étroit ;
       dans une cellule de tableau elles redeviennent du contenu de cellule,
       sans quoi chaque colonne se casse en hauteur. Pas de backtick dans ce
       commentaire : il est DANS un littéral de gabarit. */
    .tableau { width: 100%; border-collapse: collapse; table-layout: fixed; }
    .tableau th, .tableau td {
      text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--hs-divider);
      overflow-wrap: anywhere; font-size: 0.9rem;
    }
    .tableau th { font-size: 0.85rem; color: var(--hs-text-2); font-weight: 600; }
    .tableau .ligne { height: var(--hs-touch); }
    /* Le bouton d'ouverture garde la classe de la carte étroite : c'est le
       MÊME geste, et un seul sélecteur le désigne dans les deux mises en page
       — y compris pour le vérificateur de rendu, qui n'a pas à connaître deux
       noms pour une seule action. */
    .tableau .ouvrir {
      display: block; width: 100%; min-height: var(--hs-touch); text-align: left; border: none;
      border-radius: 8px; padding: 8px; margin-bottom: 0; font-size: 0.95rem;
      font-weight: 600;
      background: var(--hs-surface-2); color: var(--hs-text);
    }
  `],e([pe({attribute:!1})],_t.prototype,"connexion",void 0),e([pe({type:Boolean})],_t.prototype,"large",void 0),e([pe({attribute:!1})],_t.prototype,"file",void 0),e([de()],_t.prototype,"piles",void 0),e([de()],_t.prototype,"aDeclarer",void 0),e([de()],_t.prototype,"selection",void 0),e([de()],_t.prototype,"evenements",void 0),e([de()],_t.prototype,"armee",void 0),e([de()],_t.prototype,"refus",void 0),e([de()],_t.prototype,"ignoree",void 0),e([de()],_t.prototype,"motif",void 0),e([de()],_t.prototype,"erreurMotif",void 0),_t=e([ce("home-stock-piles")],_t);const kt="Sans emplacement";function wt(e){const[t,i,s]=e.split("-");return`${s}/${i}/${t}`}function Ct(e){return e.warranty_ends_on&&null!==e.days_left?e.days_left<0?`garantie terminée depuis le ${wt(e.warranty_ends_on)}`:`garantie jusqu’au ${wt(e.warranty_ends_on)} — ${e.days_left} jours`:"garantie non renseignée"}let At=class extends oe{constructor(){super(...arguments),this.large=!1,this.equipements=[],this.fiche=null,this.armee=null}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(!this.connexion)return;const e=await this.connexion.appeler("home_stock/equipment/list");this.equipements=e.equipment}async ouvrir(e){if(!this.connexion)return;this.armee=null;const t=await this.connexion.appeler("home_stock/equipment/get",{equipment_id:e.id});this.fiche=t.equipment}async delier(e){this.armee===e.id?(this.armee=null,this.file&&(this.file.ajouter("home_stock/equipment/consumable/unlink",{consumable_id:e.id}),this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0})),await this.file.rejouer(),this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0})),this.fiche&&await this.ouvrir(this.fiche))):this.armee=e.id}groupes(){const e=new Map;for(const t of this.equipements){const i=t.location_name??kt;e.set(i,[...e.get(i)??[],t])}return[...e.entries()].sort(([e],[t])=>e===kt?1:t===kt?-1:e.localeCompare(t))}rendreFiche(e){return I`
      <section class="section">
        <h2>${e.name}</h2>
        <span class="detail">${e.location_name??kt}</span>
        ${e.brand||e.model?I`
          <span class="detail">${[e.brand,e.model].filter(Boolean).join(" ")}</span>`:B}
        ${e.serial?I`<span class="detail">N° de série : ${e.serial}</span>`:B}
        ${e.purchased_on?I`<span class="detail">Acheté le ${wt(e.purchased_on)}</span>`:I`<span class="detail">Date d’achat non renseignée</span>`}
        <span class="detail">${Ct(e)}</span>
        ${e.manual_media_id||e.manual_url?I`
          <span class="detail lien">
            Notice : ${e.manual_url??e.manual_media_id}
            ${e.manual_introuvable?" — fichier introuvable":""}
          </span>`:I`<span class="detail">Notice non renseignée</span>`}

        <h2>Consommables</h2>
        ${0===e.consumables.length?I`<span class="detail">Aucun consommable rattaché.</span>`:e.consumables.map(e=>I`
              <div class="equipement">
                <span class="libelle">${e.product_name}</span>
                <span class="detail">
                  ${e.label??e.role} — ${function(e){const t=e.in_stock??0;return t<=0?"aucun en stock":`${Number.isInteger(t)?t:t.toFixed(1)} en stock`}(e)}
                </span>
                ${null!==e.low_value?I`
                  <span class="detail">
                    Seuils : ${e.low_value} / ${e.keep_value}
                    ${"percent"===e.unit?"%":e.unit??""}
                  </span>`:B}
              </div>
              <button class="action delier" @click=${()=>this.delier(e)}>
                ${this.armee===e.id?"Confirmer : délier ce consommable":"Délier ce consommable"}
              </button>
            `)}

        <h2>Piles</h2>
        ${0===e.batteries.length?I`<span class="detail">Aucune pile rattachée.</span>`:e.batteries.map(e=>I`
              <span class="detail">
                ${e.label} — ${e.verb}${null!==e.last_percent?` — ${Math.trunc(e.last_percent)} %`:" — jamais relevée"}
              </span>`)}

        <button class="action" @click=${()=>{this.fiche=null,this.armee=null}}>
          Retour à la liste
        </button>
      </section>
    `}rendreTableau(){return I`
      <table class="tableau">
        <thead>
          <tr><th>Appareil</th><th>Emplacement</th><th>Garantie</th><th>Consommables</th></tr>
        </thead>
        <tbody>
          ${this.equipements.map(e=>I`
            <tr class="ligne">
              <td class="libelle">
                <button class="equipement ouvrir" @click=${()=>this.ouvrir(e)}>
                  ${e.name}
                </button>
              </td>
              <td class="detail">${e.location_name??"Sans emplacement"}</td>
              <td class="detail">${Ct(e)}</td>
              <td class="detail">${e.consumable_count||"—"}</td>
            </tr>
          `)}
        </tbody>
      </table>
    `}render(){return this.fiche?this.rendreFiche(this.fiche):this.large?this.rendreTableau():I`
      ${this.groupes().map(([e,t])=>I`
        <section class="section">
          <h2 class="emplacement">${e}</h2>
          ${t.map(e=>I`
            <button class="equipement" @click=${()=>this.ouvrir(e)}>
              <span class="libelle">${e.name}</span>
              <span class="detail">${Ct(e)}</span>
              ${e.consumable_count?I`<span class="detail">${e.consumable_count} consommable(s)</span>`:B}
            </button>
          `)}
        </section>
      `)}
    `}};At.styles=[we,a`
    :host { display: block; padding: 12px; color: var(--hs-text); box-sizing: border-box; }
    * { box-sizing: border-box; max-width: 100%; }
    /* Un entity_id est long et sans espace (sensor.browser_mod_606bfd06_
       browser_battery) : sans coupure, il pousse la page au-delà des 412 px
       de la dalle du téléphone, et le vérificateur de rendu le refuse — à
       juste titre. Pas de backtick dans ce commentaire : il est DANS un
       littéral de gabarit, et il le terminerait. */
    .libelle, .detail, .verbe, .lien { overflow-wrap: anywhere; }
    h2 { font-size: 1rem; margin: 12px 0 8px; }
    .equipement {
      display: block; width: 100%; min-height: var(--hs-touch); text-align: left;
      margin-bottom: 8px; padding: 10px 12px; border: none; border-radius: 8px;
      background: var(--hs-surface-2); color: var(--hs-text);
      font-size: 0.95rem;
    }
    .libelle { display: block; font-weight: 600; }
    .detail { display: block; font-size: 0.85rem; }
    button.action {
      min-height: var(--hs-touch); width: 100%; border-radius: 8px; border: none;
      margin-bottom: 8px; font-size: 0.95rem;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    button.delier { background: var(--hs-surface-2); color: var(--hs-text); }
    .lien { word-break: break-all; }

    /* --- la vue dense (lot 6), au-delà de 1000 px ------------------------- */
    .tableau { width: 100%; border-collapse: collapse; table-layout: fixed; }
    .tableau th, .tableau td {
      text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--hs-divider);
      overflow-wrap: anywhere; font-size: 0.9rem;
    }
    .tableau th { font-size: 0.85rem; color: var(--hs-text-2); font-weight: 600; }
    .tableau .ligne { height: var(--hs-touch); }
    /* Le bouton d'ouverture garde la classe de la carte étroite : c'est le
       MÊME geste, et un seul sélecteur le désigne dans les deux mises en page
       — y compris pour le vérificateur de rendu, qui n'a pas à connaître deux
       noms pour une seule action. */
    .tableau .ouvrir {
      display: block; width: 100%; min-height: var(--hs-touch); text-align: left; border: none;
      border-radius: 8px; padding: 8px; margin-bottom: 0; font-size: 0.95rem;
      font-weight: 600;
      background: var(--hs-surface-2); color: var(--hs-text);
    }
  `],e([pe({attribute:!1})],At.prototype,"connexion",void 0),e([pe({type:Boolean})],At.prototype,"large",void 0),e([pe({attribute:!1})],At.prototype,"file",void 0),e([de()],At.prototype,"equipements",void 0),e([de()],At.prototype,"fiche",void 0),e([de()],At.prototype,"armee",void 0),At=e([ce("home-stock-equipements")],At);let Et=class extends oe{constructor(){super(...arguments),this.donnees=null,this.large=!1,this.enAttente=0,this.cocheesLocalement=new Set,this.decocheesLocalement=new Set,this.retireesLocalement=new Set,this.saisie=""}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){this.connexion&&(this.donnees=await this.connexion.appeler("home_stock/list/items"),this.cocheesLocalement=new Set,this.decocheesLocalement=new Set,this.retireesLocalement=new Set)}ecrire(e,t){this.file&&(this.file.ajouter(e,t),this.avertirFile(),this.file.rejouer().then(()=>{this.avertirFile(),this.charger()}))}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}estCochee(e){return!this.decocheesLocalement.has(e.id)&&(this.cocheesLocalement.has(e.id)||null!==e.checked_at)}cocher(e){this.cocheesLocalement=new Set(this.cocheesLocalement).add(e.id);const t=new Set(this.decocheesLocalement);t.delete(e.id),this.decocheesLocalement=t,this.ecrire("home_stock/list/check",{item_id:e.id})}decocher(e){this.decocheesLocalement=new Set(this.decocheesLocalement).add(e.id);const t=new Set(this.cocheesLocalement);t.delete(e.id),this.cocheesLocalement=t,this.ecrire("home_stock/list/uncheck",{item_id:e.id})}retirer(e){this.retireesLocalement=new Set(this.retireesLocalement).add(e.id),this.ecrire("home_stock/list/remove",{item_id:e.id})}ajouter(){const e=this.saisie.trim();e&&(this.ecrire("home_stock/list/add",{free_text:e}),this.saisie="")}origines(e){return e.claims.map(e=>e.detail).filter(Boolean).join(" · ")}rendreLigne(e,t){const i=e.product_name??e.free_text??"",s=this.origines(e);return I`
      <article class="ligne ${t?"ligne-cochee":""}">
        <button class=${t?"decocher":"cocher"}
          aria-label=${t?`Décocher ${i}`:`Cocher ${i}`}
          @click=${()=>t?this.decocher(e):this.cocher(e)}>
          ${t?"☑":"☐"}
        </button>
        <div class="infos">
          <p class="nom">${i}</p>
          <p class="quantite">${function(e){if(null===e.quantity)return"ce qu’il faut";const t=e.base_unit&&"piece"!==e.base_unit?` ${e.base_unit}`:"";return`${e.quantity}${t}`}(e)}</p>
          ${s?I`<p class="origines">${s}</p>`:B}
        </div>
        <button class="retirer" aria-label=${`Retirer ${i} de la liste`}
          @click=${()=>this.retirer(e)}>×</button>
      </article>
    `}render(){const e=this.donnees;if(!e)return I`<p class="vide">Liste indisponible.</p>`;const t=e.items.filter(e=>!this.retireesLocalement.has(e.id)),i=t.filter(e=>!this.estCochee(e)),s=t.filter(e=>this.estCochee(e)),r=e.estimate;return I`
      <section class="bandeau">
        <p class="magasin">${e.store_name??"Ordre par défaut"}</p>
        <p class="compte">${`${i.length} ligne${i.length>1?"s":""} — ≈ ${n=r.amount,`${n.toFixed(2).replace(".",",")} €`}`}</p>
        <p class="confiance">${`estimation sur ${r.priced} ligne${r.priced>1?"s":""} sur ${r.total}`}</p>
      </section>

      ${this.enAttente>0?I`
        <p class="en-attente">
          ${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau
        </p>
      `:B}

      <section class="ajout">
        <input class="champ-ajout" .value=${this.saisie} placeholder="Ajouter une ligne"
          aria-label="Ajouter une ligne"
          @input=${e=>{this.saisie=e.target.value}} />
        <button class="ajouter" @click=${this.ajouter}>Ajouter</button>
      </section>

      ${0===i.length?I`
        <p class="vide">Rien à acheter pour l’instant.</p>
      `:B}

      ${(()=>{const e=function(e){const t=[];for(const i of e){const e=i.aisle_name??"Sans rayon",s=t[t.length-1];s&&s.rayon===e?s.lignes.push(i):t.push({rayon:e,lignes:[i]})}return t}(i).map(e=>I`
          <section class="rayon">
            <h3 class="rayon-nom">${e.rayon}</h3>
            ${e.lignes.map(e=>this.rendreLigne(e,!1))}
          </section>
        `);return this.large?I`<div class="rayons-colonnes">${e}</div>`:e})()}

      ${s.length>0?I`
        <section class="cochees">
          <h3 class="rayon-nom">Dans le chariot (${s.length})</h3>
          ${s.map(e=>this.rendreLigne(e,!0))}
        </section>
      `:B}
    `;var n}};Et.styles=[we,a`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--hs-text); }
    .bandeau {
      display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px;
      justify-content: space-between; margin-bottom: 8px;
    }
    .magasin { font-weight: 600; margin: 0; }
    .compte { font-size: 1.2rem; font-weight: 700; margin: 0; }
    .confiance { font-size: 0.8rem; color: var(--hs-text-2); margin: 0; flex-basis: 100%; }
    .en-attente { text-align: center; color: var(--hs-text-2); font-size: 0.85rem; margin: 4px 0 8px; }
    .ajout { display: flex; gap: 8px; margin-bottom: 8px; }
    .champ-ajout { flex: 1; min-height: var(--hs-touch); box-sizing: border-box; font-size: 1rem; padding: 4px 8px; }
    .ajouter {
      min-height: var(--hs-touch); min-width: var(--hs-touch); border-radius: 8px; border: none;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .vide { color: var(--hs-text-2); text-align: center; }
    .rayon-nom {
      margin: 16px 0 4px; font-size: 0.9rem; text-transform: uppercase;
      color: var(--hs-text-2); letter-spacing: 0.04em;
    }

    /* --- la vue dense (lot 6) ---------------------------------------------
       Des colonnes d'au moins 320 px : en dessous, le nom, la quantité et
       l'origine d'une ligne se cassent en trois et on perd tout le gain.
       Le remplissage automatique laisse le nombre de colonnes suivre la largeur
       réelle, plutôt que de le figer à trois. */
    .rayons-colonnes {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 0 24px; align-items: start;
    }
    .rayons-colonnes .rayon { break-inside: avoid; }
    .ligne {
      display: flex; align-items: center; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--hs-divider);
    }
    .ligne-cochee .nom { text-decoration: line-through; color: var(--hs-text-2); }
    .cocher, .decocher {
      min-width: var(--hs-touch); min-height: var(--hs-touch); border-radius: 8px; border: none; font-size: 1.3rem;
      background: var(--hs-surface-2); color: var(--hs-text); flex-shrink: 0;
    }
    .infos { flex: 1; min-width: 0; }
    .nom { margin: 0; }
    .quantite { margin: 2px 0 0; font-size: 0.9rem; color: var(--hs-text-2); }
    .origines { margin: 2px 0 0; font-size: 0.8rem; color: var(--hs-text-2); }
    .retirer {
      min-width: var(--hs-touch); min-height: var(--hs-touch); border-radius: 8px; border: none; font-size: 1.2rem;
      background: var(--hs-surface-2); color: var(--hs-text); flex-shrink: 0;
    }
  `],e([pe({attribute:!1})],Et.prototype,"donnees",void 0),e([pe({attribute:!1})],Et.prototype,"connexion",void 0),e([pe({type:Boolean})],Et.prototype,"large",void 0),e([pe({attribute:!1})],Et.prototype,"file",void 0),e([pe({attribute:!1})],Et.prototype,"enAttente",void 0),e([de()],Et.prototype,"cocheesLocalement",void 0),e([de()],Et.prototype,"decocheesLocalement",void 0),e([de()],Et.prototype,"retireesLocalement",void 0),e([de()],Et.prototype,"saisie",void 0),Et=e([ce("home-stock-liste")],Et);const qt={pending:"Lecture en cours…",read:"Ticket lu",failed:"Lecture impossible",applied:"Prix appliqués",discarded:"Ticket abandonné"};function Lt(e){return`${e.toFixed(2).replace(".",",")} €`}let St=class extends oe{constructor(){super(...arguments),this.ticket=null,this.large=!1,this.enAttente=0,this.agentConfigure=!0,this.erreur=null,this.applicationArmee=!1}ecrire(e,t){this.file&&(this.file.ajouter(e,t),this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()))}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}async surPhoto(e){const t=e.target,i=t.files?.[0],s=this.televerser??(e=>this.connexion.televerserMedia(e,"media-source://media_source/local/home_stock/receipts"));if(!i||!this.televerser&&!this.connexion)return;let r;this.erreur=null;try{r=await s(i)}catch(e){return void(this.erreur=function(e){const t=String(e?.message??e);return t.includes("403")||t.includes("401")?"Le téléversement demande un compte administrateur : connectez-vous avec celui du foyer.":t.includes("413")?"Photo refusée : elle dépasse 20 Mo. Reprenez-la en moins grand.":t.includes("415")||t.toLowerCase().includes("image")?"Photo refusée : seules les images sont acceptées.":`Le téléversement a échoué (${t}).`}(e))}this.ecrire("home_stock/receipt/submit",{media_content_id:r})}rapprocher(e,t){this.ecrire("home_stock/receipt/line/match",{line_id:e.id,shopping_line_id:t,state:"confirmed"})}ignorer(e){this.ecrire("home_stock/receipt/line/match",{line_id:e.id,shopping_line_id:null,state:"ignored"})}reessayer(){this.ticket&&this.ecrire("home_stock/receipt/retry",{receipt_id:this.ticket.id})}appliquer(){this.ticket&&(this.ecrire("home_stock/receipt/apply",{receipt_id:this.ticket.id}),this.applicationArmee=!1)}mouvementsACorriger(){const e=this.ticket;if(!e)return 0;const t=new Set(e.lines.filter(e=>null!==e.line_id&&"ignored"!==e.match_state).map(e=>e.line_id));return e.cart_lines.filter(e=>t.has(e.id)).reduce((e,t)=>e+(t.movements??0),0)}chariotPour(e){return null===e.line_id?null:this.ticket?.cart_lines.find(t=>t.id===e.line_id)??null}rendreLigne(e){const t=this.chariotPour(e),i=e.candidates[0]??null;return I`
      <article class="ligne-ticket">
        <div class="cote-ticket">
          <p class="libelle">${e.label}</p>
          <p class="prix">${null===e.total_price?"—":Lt(e.total_price)}</p>
        </div>
        <div class="cote-chariot">
          ${t?I`
            <p class="rapproche">${t.article_label??t.product_name}</p>
          `:I`
            <p class="orphelin">Aucune ligne de panier — Scanner l’article pour la rattacher</p>
          `}
          ${"ignored"===e.match_state?I`<p class="ignoree">Ignorée</p>`:B}
        </div>
        <div class="actions-ligne">
          ${i?I`
            <button class="rapprocher" @click=${()=>this.rapprocher(e,i.line_id)}>
              ${i.label}
            </button>
          `:B}
          <button class="ignorer" @click=${()=>this.ignorer(e)}>Ignorer</button>
        </div>
      </article>
    `}render(){if(!this.agentConfigure)return I`
        <p class="vide">
          Aucune entité de lecture n’est configurée : choisissez-en une dans les
          réglages du garde-manger pour photographier vos tickets.
        </p>`;const e=this.ticket;return I`
      ${this.enAttente>0?I`
        <p class="en-attente">
          ${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau
        </p>
      `:B}

      ${null===e?I`
        <section class="bloc-principal">
          <label class="prendre-photo">
            Photographier le ticket
            <input class="photo" type="file" accept="image/*" capture="environment"
              @change=${this.surPhoto} />
          </label>
        </section>
      `:this.rendreTicket(e)}

      ${this.erreur?I`<p class="erreur">${this.erreur}</p>`:B}
    `}rendreTicket(e){const t=this.mouvementsACorriger();return I`
      <section class="entete">
        <p class="etat">${qt[e.state]}</p>
        ${null!==e.total?I`
          <p class="total">${Lt(e.total)}</p>
        `:B}
      </section>

      ${e.error?I`<p class="erreur">${e.error}</p>`:B}

      ${null!==e.total_gap?I`
        <p class="ecart">
          ${`La somme des lignes s’écarte du total de ${Lt(Math.abs(e.total_gap))}.`}
        </p>
      `:B}

      ${"failed"===e.state?I`
        <button class="reessayer" @click=${this.reessayer}>Réessayer la lecture</button>
      `:B}

      ${this.large?I`
        <div class="deux-volets">
          <aside class="volet-ticket">
            <h2 class="titre-volet">Ticket lu</h2>
            ${e.raw?I`<pre class="texte-lu">${e.raw}</pre>`:I`<p class="pas-encore-lu">Le ticket n’a pas encore été lu :
                  rien à comparer pour l’instant.</p>`}
          </aside>
          <section class="bloc-principal volet-lignes">
            ${e.lines.map(e=>this.rendreLigne(e))}
          </section>
        </div>
      `:I`
        <section class="bloc-principal">
          ${e.lines.map(e=>this.rendreLigne(e))}
        </section>
      `}

      ${this.applicationArmee?I`
        <div class="confirmation">
          <p class="avertissement">${0===t?"Aucun mouvement déjà écrit ne sera corrigé.":`${t} mouvement${t>1?"s":""} déjà écrit${t>1?"s":""} seront corrigés.`}</p>
          <button class="confirmer-application" @click=${this.appliquer}>Confirmer</button>
          <button class="annuler-application"
            @click=${()=>{this.applicationArmee=!1}}>Annuler</button>
        </div>
      `:I`
        <button class="appliquer" ?disabled=${"read"!==e.state}
          @click=${()=>{this.applicationArmee=!0}}>
          Appliquer les prix
        </button>
      `}
    `}};St.styles=[we,a`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--hs-text); }
    .vide { color: var(--hs-text-2); text-align: center; }
    .en-attente { text-align: center; color: var(--hs-text-2); font-size: 0.85rem; margin: 4px 0 8px; }
    .entete { display: flex; justify-content: space-between; align-items: baseline; }
    .etat { font-weight: 600; margin: 0; }
    .total { font-size: 1.3rem; font-weight: 700; margin: 0; }
    /* Pas d'aplat sous du texte (§ 6.1 ter) : le texte reste --hs-text, la
       bordure porte --hs-danger. */
    .erreur {
      margin: 8px 0; padding: 8px 12px; border-radius: 8px;
      background: var(--hs-surface); color: var(--hs-text); font-size: 0.9rem;
      border-left: 4px solid var(--hs-danger);
    }
    .ecart {
      color: var(--hs-text); border-left: 3px solid var(--hs-warning);
      padding-left: 8px; font-size: 0.9rem; margin: 8px 0;
    }
    .prendre-photo {
      display: block; min-height: var(--hs-touch); padding: 16px; border-radius: 12px; text-align: center;
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .photo { display: block; margin: 8px auto 0; color: inherit; }
    /* --- la vue dense (lot 6), au-delà de 1000 px --------------------------
       Rapprocher, c'est COMPARER : le texte lu d'un côté, les lignes de
       l'autre, sans défiler entre les deux. La colonne du ticket est bornée à
       360 px et jamais à une fraction de la largeur — un ticket de caisse est
       haut et étroit, et lui donner la moitié d'un 1920 l'étirerait en lignes
       illisibles tout en écrasant le vrai travail de l'écran, qui est à
       droite. Elle défile pour elle-même, sans emporter la page. */
    .deux-volets {
      display: grid; grid-template-columns: minmax(0, 360px) minmax(0, 1fr);
      gap: 16px; align-items: start; margin-top: 8px;
    }
    .volet-ticket {
      background: var(--hs-surface-2); border-radius: 8px; padding: 8px 12px;
      max-height: 70vh; overflow: auto; min-width: 0;
    }
    .titre-volet { font-size: 0.9rem; margin: 0 0 8px; color: var(--hs-text-2); }
    .texte-lu { margin: 0; font-family: monospace; font-size: 0.85rem; white-space: pre-wrap;
                overflow-wrap: anywhere; }
    .pas-encore-lu { margin: 0; font-size: 0.9rem; color: var(--hs-text-2); }
    .volet-lignes { min-width: 0; }
    .ligne-ticket {
      display: flex; flex-wrap: wrap; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--hs-divider);
    }
    .cote-ticket { flex: 1 1 40%; min-width: 0; }
    .cote-chariot { flex: 1 1 40%; min-width: 0; }
    .libelle { margin: 0; font-family: monospace; }
    .prix { margin: 2px 0 0; font-size: 0.9rem; color: var(--hs-text-2); }
    .rapproche { margin: 0; }
    .orphelin, .ignoree { margin: 0; font-size: 0.85rem; color: var(--hs-text-2); }
    .actions-ligne { display: flex; gap: 8px; flex-basis: 100%; }
    .rapprocher, .ignorer, .reessayer {
      min-height: var(--hs-touch); min-width: var(--hs-touch); border-radius: 8px; border: none; font-size: 0.9rem;
      background: var(--hs-surface-2); color: var(--hs-text);
    }
    .appliquer, .confirmer-application, .annuler-application {
      display: block; width: 100%; min-height: var(--hs-touch); font-size: 1.1rem; border-radius: 12px;
      border: none; margin-top: 12px;
    }
    .appliquer, .confirmer-application {
      background: var(--hs-accent); color: var(--hs-on-accent);
    }
    .appliquer:disabled { opacity: 0.5; }
    .annuler-application {
      background: var(--hs-surface-2); color: var(--hs-text);
    }
    .avertissement { margin: 12px 0 0; font-size: 0.9rem; }
  `],e([pe({attribute:!1})],St.prototype,"ticket",void 0),e([pe({attribute:!1})],St.prototype,"connexion",void 0),e([pe({type:Boolean})],St.prototype,"large",void 0),e([pe({attribute:!1})],St.prototype,"file",void 0),e([pe({attribute:!1})],St.prototype,"enAttente",void 0),e([pe({attribute:!1})],St.prototype,"agentConfigure",void 0),e([pe({attribute:!1})],St.prototype,"televerser",void 0),e([de()],St.prototype,"erreur",void 0),e([de()],St.prototype,"applicationArmee",void 0),St=e([ce("home-stock-ticket")],St);const Pt={cart:"M17,18C15.89,18 15,18.89 15,20A2,2 0 0,0 17,22A2,2 0 0,0 19,20C19,18.89 18.1,18 17,18M1,2V4H3L6.6,11.59L5.24,14.04C5.09,14.32 5,14.65 5,15A2,2 0 0,0 7,17H19V15H7.42A0.25,0.25 0 0,1 7.17,14.75C7.17,14.7 7.18,14.66 7.2,14.63L8.1,13H15.55C16.3,13 16.96,12.58 17.3,11.97L20.88,5.5C20.95,5.34 21,5.17 21,5A1,1 0 0,0 20,4H5.21L4.27,2M7,18C5.89,18 5,18.89 5,20A2,2 0 0,0 7,22A2,2 0 0,0 9,20C9,18.89 8.1,18 7,18Z",package:"M2,10.96C1.5,10.68 1.35,10.07 1.63,9.59L3.13,7C3.24,6.8 3.41,6.66 3.6,6.58L11.43,2.18C11.59,2.06 11.79,2 12,2C12.21,2 12.41,2.06 12.57,2.18L20.47,6.62C20.66,6.72 20.82,6.88 20.91,7.08L22.36,9.6C22.64,10.08 22.47,10.69 22,10.96L21,11.54V16.5C21,16.88 20.79,17.21 20.47,17.38L12.57,21.82C12.41,21.94 12.21,22 12,22C11.79,22 11.59,21.94 11.43,21.82L3.53,17.38C3.21,17.21 3,16.88 3,16.5V10.96C2.7,11.13 2.32,11.14 2,10.96M12,4.15V4.15L12,10.85V10.85L17.96,7.5L12,4.15M5,15.91L11,19.29V12.58L5,9.21V15.91M19,15.91V12.5L13,15.86V19.29L19,15.91M13.85,13.36L19.5,10.5L18.5,8.75L13.85,13.36Z",cutlery:"M11,9H9V2H7V9H5V2H3V9C3,11.12 4.66,12.84 6.75,12.97V22H9.25V12.97C11.34,12.84 13,11.12 13,9V2H11V9M16,6V14H18.5V22H21V2C18.24,2 16,4.24 16,6Z",home:"M12,3L2,12H5V20H19V12H22L12,3M12,7.7L17,12.2V18H15V14H9V18H7V12.2L12,7.7Z",back:"M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z",scan:"M4,6H6V18H4V6M7,6H8V18H7V6M9,6H12V18H9V6M13,6H14V18H13V6M16,6H18V18H16V6M19,6H20V18H19V6M2,4V8H0V4A2,2 0 0,1 2,2H6V4H2M22,2A2,2 0 0,1 24,4V8H22V4H18V2H22M2,16V20H6V22H2A2,2 0 0,1 0,20V16H2M22,20V16H24V20A2,2 0 0,1 22,22H18V20H22Z",plus:"M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z",check:"M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z",close:"M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z",search:"M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z",settings:"M12,8A4,4 0 0,1 16,12A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10M10,22C9.75,22 9.54,21.82 9.5,21.58L9.13,18.93C8.5,18.68 7.96,18.34 7.44,17.94L4.95,18.95C4.73,19.03 4.46,18.95 4.34,18.73L2.34,15.27C2.21,15.05 2.27,14.78 2.46,14.63L4.57,12.97L4.5,12L4.57,11L2.46,9.37C2.27,9.22 2.21,8.95 2.34,8.73L4.34,5.27C4.46,5.05 4.73,4.96 4.95,5.05L7.44,6.05C7.96,5.66 8.5,5.32 9.13,5.07L9.5,2.42C9.54,2.18 9.75,2 10,2H14C14.25,2 14.46,2.18 14.5,2.42L14.87,5.07C15.5,5.32 16.04,5.66 16.56,6.05L19.05,5.05C19.27,4.96 19.54,5.05 19.66,5.27L21.66,8.73C21.79,8.95 21.73,9.22 21.54,9.37L19.43,11L19.5,12L19.43,13L21.54,14.63C21.73,14.78 21.79,15.05 21.66,15.27L19.66,18.73C19.54,18.95 19.27,19.04 19.05,18.95L16.56,17.95C16.04,18.34 15.5,18.68 14.87,18.93L14.5,21.58C14.46,21.82 14.25,22 14,22H10M11.25,4L10.88,6.61C9.68,6.86 8.62,7.5 7.85,8.39L5.44,7.35L4.69,8.65L6.8,10.2C6.4,11.37 6.4,12.64 6.8,13.8L4.68,15.36L5.43,16.66L7.86,15.62C8.63,16.5 9.68,17.14 10.87,17.38L11.24,20H12.76L13.13,17.39C14.32,17.14 15.37,16.5 16.14,15.62L18.57,16.66L19.32,15.36L17.2,13.81C17.6,12.64 17.6,11.37 17.2,10.2L19.31,8.65L18.56,7.35L16.15,8.39C15.38,7.5 14.32,6.86 13.12,6.62L12.75,4H11.25Z",battery:"M12,2A2,2 0 0,1 14,4V6H15A2,2 0 0,1 17,8V20A2,2 0 0,1 15,22H9A2,2 0 0,1 7,20V8A2,2 0 0,1 9,6H10V4A2,2 0 0,1 12,2M9,8V20H15V8H9M11,10H13V15H11V10M11,16H13V18H11V16Z",menu:"M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z",alert:"M11,15H13V17H11V15M11,7H13V13H11V7M12,2C6.47,2 2,6.5 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20Z",clock:"M12,20A8,8 0 0,0 20,12A8,8 0 0,0 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22C6.47,22 2,17.5 2,12A10,10 0 0,1 12,2M12.5,7V12.25L17,14.92L16.25,16.15L11,13V7H12.5Z"},zt=new Map;let Mt=!1;function jt(e){return"undefined"!=typeof customElements&&Boolean(customElements.get(e))}const Rt="ha-svg-icon";let Ft=class extends oe{constructor(){super(...arguments),this.name="home",this.label=null,this.annulerAbonnementHaSvgIcon=null}connectedCallback(){super.connectedCallback(),this.annulerAbonnementHaSvgIcon=function(e,t){if(jt(e))return()=>{};const i=zt.get(e);return i?i.push(t):(zt.set(e,[t]),customElements.whenDefined(e).then(()=>{for(const t of zt.get(e)??[])t();zt.delete(e)})),()=>{const i=zt.get(e);if(!i)return;const s=i.indexOf(t);s>=0&&i.splice(s,1),0===i.length&&zt.delete(e)}}(Rt,()=>this.requestUpdate())}disconnectedCallback(){super.disconnectedCallback(),this.annulerAbonnementHaSvgIcon?.(),this.annulerAbonnementHaSvgIcon=null}willUpdate(){this.label?(this.setAttribute("role","img"),this.setAttribute("aria-label",this.label),this.removeAttribute("aria-hidden")):(this.removeAttribute("role"),this.removeAttribute("aria-label"),this.setAttribute("aria-hidden","true"))}render(){const e=Pt[this.name];return jt(Rt)?I`<ha-svg-icon .path=${e}></ha-svg-icon>`:I`
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d=${e}></path>
      </svg>`}};Ft.styles=[we,a`
    :host { display: inline-flex; width: 24px; height: 24px; }
    svg, ha-svg-icon { width: 100%; height: 100%; fill: currentColor; }
  `],e([pe({type:String})],Ft.prototype,"name",void 0),e([pe({type:String})],Ft.prototype,"label",void 0),Ft=e([ce("hs-icon")],Ft);const Vt=[{id:"shopping",label:"Courses",icon:"cart",root:"liste"},{id:"stock",label:"Stock",icon:"package",root:"catalogue"},{id:"kitchen",label:"Cuisine",icon:"cutlery",root:"planning"},{id:"house",label:"Maison",icon:"home",root:"piles"}],Ot=[{screen:"liste",label:"Liste de courses",family:"shopping",segment:"list",root:!0},{screen:"session",label:"Courses",family:"shopping",segment:"shopping",root:!1},{screen:"panier",label:"Panier",family:"shopping",segment:"cart",root:!1},{screen:"rangement",label:"Rangement",family:"shopping",segment:"put-away",root:!1},{screen:"ticket",label:"Ticket",family:"shopping",segment:"receipt",param:"id",root:!1},{screen:"scanner",label:"Scanner",family:"shopping",segment:"scan",root:!1},{screen:"fiche",label:"Article",family:"shopping",segment:"item",param:"code",root:!1},{screen:"catalogue",label:"Catalogue",family:"stock",segment:"catalog",root:!0},{screen:"journal",label:"Journal",family:"stock",segment:"log",root:!1},{screen:"consommation",label:"Manger",family:"stock",segment:"eat",param:"id",root:!1},{screen:"planning",label:"Planning",family:"kitchen",segment:"planner",root:!0},{screen:"recettes",label:"Recettes",family:"kitchen",segment:"recipes",root:!1},{screen:"recette",label:"Recette",family:"kitchen",segment:"recipe",param:"id",root:!1},{screen:"validation",label:"Validation du repas",family:"kitchen",segment:"validate",param:"id",root:!1},{screen:"piles",label:"Piles",family:"house",segment:"batteries",root:!0},{screen:"equipements",label:"Équipements",family:"house",segment:"equipment",root:!1},{screen:"reglages",label:"Réglages",family:"house",segment:"settings",root:!1}],Nt=new Map(Ot.map(e=>[e.screen,e]));function Ht(e){const t=Nt.get(e);if(!t)throw new Error(`Écran hors de la table des destinations : ${e}`);return t}function Tt(e){return Ht(e).family}let Dt=class extends oe{constructor(){super(...arguments),this.current="liste",this.rail=!1,this.badges={}}choisir(e){this.dispatchEvent(new CustomEvent("famille-choisie",{detail:{family:e},bubbles:!0,composed:!0}))}render(){const e=Tt(this.current);return I`
      <nav class="barre ${this.rail?"rail":""}">
        ${Vt.map(t=>{const i=this.badges[t.id]??0,s=t.id===e;return I`
            <button class="destination ${s?"active":""}"
                    data-family=${t.id}
                    aria-current=${s?"page":B}
                    aria-label=${i>0?`${t.label}, ${i} en attente`:t.label}
                    @click=${()=>this.choisir(t.id)}>
              <hs-icon name=${t.icon}></hs-icon>
              <span>${t.label}</span>
              ${i>0?I`<span class="badge">${i}</span>`:B}
            </button>`})}
      </nav>`}};Dt.styles=[we,a`
    :host { display: block; }
    .barre {
      display: flex; background: var(--hs-surface);
      border-top: 1px solid var(--hs-divider);
    }
    .barre.rail {
      flex-direction: column;
      border-top: none; border-right: 1px solid var(--hs-divider);
      height: 100%;
    }
    .destination {
      flex: 1 1 0; position: relative;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      gap: var(--hs-space-1);
      min-height: var(--hs-touch); min-width: var(--hs-touch);
      padding: var(--hs-space-2) var(--hs-space-1);
      border: none; background: none; cursor: pointer;
      font-family: var(--hs-font); font-size: 0.75rem;
      color: var(--hs-text-2);
    }
    .barre.rail .destination { flex: 0 0 auto; }
    /* L'accent NE PEUT PAS servir de couleur de texte ici : posé sur
       --hs-surface, il donne 3,26:1 sous le thème HA par défaut et 2,38:1
       sous Graphite (en service dans la maison) — les deux sous le seuil de
       4,5:1, relevé par outils/verifier-rendu.mjs dès que la barre a été
       branchée au panneau. L'état actif se dit donc par la GRAISSE du
       libellé, qui garde le contraste du texte ordinaire, et par une pastille
       d'accent derrière l'icône — un aplat, avec sa paire --hs-on-accent
       recalculée par on-color.ts, donc lisible sous n'importe quel thème.
       C'est aussi le motif de la barre de navigation Material 3. */
    .destination.active { color: var(--hs-text); font-weight: 600; }
    .destination.active hs-icon {
      box-sizing: content-box;
      padding: 2px 12px;
      border-radius: 999px;
      background: var(--hs-accent);
      color: var(--hs-on-accent);
    }
    .badge {
      position: absolute; top: var(--hs-space-1);
      /* Décalé vers la droite du centre : la pastille se pose sur l'angle de
         l'icône, pas sur le libellé. */
      left: 56%;
      min-width: 18px; height: 18px; box-sizing: border-box;
      padding: 0 4px; border-radius: 9px;
      background: var(--hs-accent); color: var(--hs-on-accent);
      font-size: 0.7rem; line-height: 18px; text-align: center;
    }
  `],e([pe({attribute:!1})],Dt.prototype,"current",void 0),e([pe({type:Boolean})],Dt.prototype,"rail",void 0),e([pe({attribute:!1})],Dt.prototype,"badges",void 0),Dt=e([ce("hs-nav-bar")],Dt);let It=class extends oe{constructor(){super(...arguments),this.current="liste",this.pending=0,this.error=null}render(){const e=Ht(this.current);return I`
      <div class="barre">
        ${e.root?B:I`
          <button class="retour" aria-label="Retour" @click=${()=>this.dispatchEvent(new CustomEvent("retour-demande",{bubbles:!0,composed:!0}))}>
            <hs-icon name="back" label="Retour"></hs-icon>
          </button>`}
        <span class="titre">${e.label}</span>
        ${this.pending>0?I`
          <span class="attente">
            <hs-icon name="clock"></hs-icon>${this.pending} en attente
          </span>`:B}
      </div>
      ${this.error?I`
        <p class="erreur" role="alert">
          <hs-icon name="alert"></hs-icon>
          <span class="message-erreur">${this.error}</span>
          <button class="fermer-erreur" @click=${()=>this.dispatchEvent(new CustomEvent("erreur-acquittee",{bubbles:!0,composed:!0}))}>OK</button>
        </p>`:B}`}};It.styles=[we,a`
    :host { display: block; }
    .barre {
      display: flex; align-items: center; gap: var(--hs-space-2);
      min-height: var(--hs-touch);
      padding: var(--hs-space-2) var(--hs-space-3);
      background: var(--hs-surface); color: var(--hs-text);
      border-bottom: 1px solid var(--hs-divider);
    }
    .retour {
      display: inline-flex; align-items: center; justify-content: center;
      min-height: var(--hs-touch); min-width: var(--hs-touch);
      border: none; background: none; color: inherit; cursor: pointer;
      border-radius: var(--hs-radius-s);
      font-family: var(--hs-font);
    }
    .titre { flex: 1; font-size: 1.15rem; font-weight: 600; }
    .attente {
      display: inline-flex; align-items: center; gap: var(--hs-space-1);
      color: var(--hs-text-2); font-size: 0.85rem;
    }
    /* Pas d'aplat rouge sous ce texte : --error-color vaut #db4437 sous le
       thème HA par défaut, une luminance au point de bascule exact où blanc et
       noir donnent tous deux 4,29:1 — sous le seuil. Le danger passe par le
       liseré et l'icône ; le texte garde 17:1. Voir spec § 6.1 ter. */
    .erreur {
      display: flex; align-items: center; gap: var(--hs-space-2);
      margin: 0; padding: var(--hs-space-2) var(--hs-space-3);
      background: var(--hs-surface); color: var(--hs-text);
      border-left: 4px solid var(--hs-danger);
      border-bottom: 1px solid var(--hs-divider);
      font-size: 0.9rem;
    }
    .erreur hs-icon { color: var(--hs-danger); flex: 0 0 auto; }
    .message-erreur { flex: 1; }
    .fermer-erreur {
      min-height: var(--hs-touch); min-width: var(--hs-touch);
      border: 1px solid var(--hs-divider); border-radius: var(--hs-radius-s);
      background: var(--hs-surface-2); color: var(--hs-text);
      font-weight: 600; cursor: pointer;
      font-family: var(--hs-font);
    }
  `],e([pe({attribute:!1})],It.prototype,"current",void 0),e([pe({type:Number})],It.prototype,"pending",void 0),e([pe({attribute:!1})],It.prototype,"error",void 0),It=e([ce("hs-header")],It);const Ut=[["--hs-accent","--hs-on-accent"],["--hs-warning","--hs-on-warning"]];function Bt(e){const t=e.trim(),i=/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/.exec(t);if(i)return[Number(i[1]),Number(i[2]),Number(i[3])];const s=/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.exec(t);if(s){const e=3===s[1].length?s[1].split("").map(e=>e+e).join(""):s[1];return[0,2,4].map(t=>parseInt(e.slice(t,t+2),16))}return null}function Jt([e,t,i]){const s=e=>{const t=e/255;return t<=.03928?t/12.92:((t+.055)/1.055)**2.4};return.2126*s(e)+.7152*s(t)+.0722*s(i)}function Qt(e,t){const[i,s]=Jt(e)>Jt(t)?[Jt(e),Jt(t)]:[Jt(t),Jt(e)];return(i+.05)/(s+.05)}function Zt(e){return Qt(e,[255,255,255])>Qt(e,[20,20,20])?"#ffffff":"#141414"}function Gt(e){const t=document.createElement("span");t.style.cssText="position:absolute;width:0;height:0;opacity:0;pointer-events:none",e.appendChild(t);try{for(const[i,s]of Ut){t.style.color=`var(${i})`;const r=Bt(getComputedStyle(t).color);r&&e.style.setProperty(s,Zt(r))}}finally{t.remove()}}const Wt=new Map(Ot.map(e=>[e.segment,e]));let Yt=class extends oe{constructor(){super(...arguments),this.narrow=!1,this.ecran="scanner",this.enAttente=0,this.session=null,this.resultatCourant=null,this.derniereFiche=null,this.enAttenteRangement=[],this.erreurFile=null,this.navigationArmee=null,this.produitAManger=null,this.dernierChemin=null,this.auRetourDuReseau=()=>{this.file?.rejouer().then(()=>{this.enAttente=this.file.taille()})},this.surCodeLu=async e=>{await this.chargerFiche(e.detail.code)},this.surArticlePret=e=>{const{articleId:t,quantite:i,prixUnitaire:s,mode:r,offDroppedFields:n}=e.detail;if("panier"===r)return this.file.ajouter("home_stock/session/add_line",{article_id:t,quantity:i,unit_price:s}),this.enAttente=this.file.taille(),this.file.rejouer().then(()=>{this.enAttente=this.file.taille()}),this.derniereFiche=function(e,t,i=[]){return e?{nom:e.off?.label??e.article?.label??e.product?.name??e.code,marque:e.off?.brand??e.article?.brand??null,image:e.off?.image??e.article?.image??null,statut:t,ignores:i}:null}(this.resultatCourant,"Ajouté au panier.",n),this.resultatCourant=null,void this.naviguerVers("scanner");const a=function(e,t,i,s){return{source:"autonome",id:`autonome-${crypto.randomUUID()}`,article_id:t,quantity:i,unit_price:s,product_name:e?.product?.name??e?.off?.label??e?.article?.label??e?.off?.generic_name??"Article",base_unit:e?.product?.base_unit??"piece",default_location_id:e?.product?.default_location_id??null,default_shelf_life_days:e?.product?.default_shelf_life_days??null,brand:e?.off?.brand??e?.article?.brand??null,image:e?.off?.image??e?.article?.image??null,net_quantity:e?.article?.net_quantity??e?.off?.net_quantity??null}}(this.resultatCourant,t,i,s);this.enAttenteRangement=[...this.enAttenteRangement,a],this.resultatCourant=null,this.naviguerVers("rangement")},this.surSessionChangee=async()=>{await this.actualiserSession(),this.naviguerVers("scanner")},this.surMangerProduit=e=>{this.produitAManger=e.detail.product_id,this.demanderNavigation("consommation",e.detail.product_id)},this.surConsommationEnregistree=()=>{this.produitAManger=null,this.naviguerVers("scanner")},this.surLigneAutonomeRangee=e=>{this.enAttenteRangement=this.enAttenteRangement.filter(t=>t.id!==e.detail.id)},this.surRangementTermine=()=>{this.navigationArmee=null,this.naviguerVers("scanner")},this.surFileChangee=()=>{this.enAttente=this.file.taille()},this.largeMesuree="undefined"!=typeof window&&window.innerWidth>=1e3,this.surRedimensionnement=()=>{this.largeMesuree=window.innerWidth>=1e3},this.ticketOuvert=null,this.agentTicketConfigure=!0,this.surAllerListe=()=>{this.demanderNavigation("liste")},this.surTicketOuvert=e=>{this.ticketOuvert=e.detail.ticket,this.agentTicketConfigure=e.detail.agent_configure??!0,this.demanderNavigation("ticket",e.detail.ticket?.id??null)},this.recetteOuverte=null,this.repasDeLaRecette=null,this.repasAValider=null,this.surRecetteOuverte=e=>{this.recetteOuverte=e.detail.recipe_id,this.repasDeLaRecette=e.detail.meal_id??null,this.demanderNavigation("recette",e.detail.recipe_id)},this.surValiderRepas=e=>{this.repasAValider=e.detail.meal_id,this.demanderNavigation("validation",e.detail.meal_id)},this.surRepasValide=()=>{this.repasAValider=null,this.demanderNavigation("planning")},this.parametreArme=null,this.confirmerNavigation=()=>{const e=this.navigationArmee,t=this.parametreArme;this.navigationArmee=null,this.parametreArme=null,e&&this.naviguerVers(e,t)},this.annulerNavigation=()=>{this.navigationArmee=null,this.parametreArme=null},this.surFamilleChoisie=e=>{const t=Vt.find(t=>t.id===e.detail.family);t&&this.demanderNavigation(t.root)},this.surRetour=()=>{const e=Vt.find(e=>e.id===Tt(this.ecran));e&&this.demanderNavigation(e.root)},this.surErreurAcquittee=()=>{this.erreurFile=null}}willUpdate(e){if(!e.has("route"))return;const t=this.route?.path??"";t!==this.dernierChemin&&(this.dernierChemin=t,this.appliquerChemin(t))}appliquerChemin(e){const t=function(e){const t=e.split("/").filter(e=>e.length>0);if(0===t.length)return null;const i=Wt.get(t[0]);return i?i.param?t.length<2?null:{screen:i.screen,param:t[1]}:{screen:i.screen,param:null}:null}(e),i=t?t.screen:"liste";if(this.departARisque(i))return this.armer(i,t?.param??null),void this.naviguerVers("rangement",null,!0);t?(this.ecran=t.screen,this.appliquerParametre(t.screen,t.param)):this.naviguerVers("liste",null,!0)}appliquerParametre(e,t){null!==t&&("recette"===e?this.recetteOuverte=Number(t):"validation"===e?this.repasAValider=Number(t):"consommation"===e?this.produitAManger=Number(t):"ticket"===e?this.chargerTicket(Number(t)):"fiche"===e&&this.chargerFiche(t,!1))}async chargerTicket(e){this.agentTicketConfigure=!0,this.ticketOuvert=null;try{this.ticketOuvert=await this.connexion.appeler("home_stock/receipt/get",{receipt_id:e})}catch{this.erreurFile=`Ticket n° ${e} introuvable ou injoignable.`}}connectedCallback(){super.connectedCallback(),function(e=window){if(Mt)return;Mt=!0;const t=e.loadCardHelpers;if("function"==typeof t)try{Promise.resolve(t.call(e)).catch(()=>{})}catch{}}(),window.addEventListener("resize",this.surRedimensionnement),this.addEventListener("recette-ouverte",this.surRecetteOuverte),this.addEventListener("valider-repas",this.surValiderRepas),this.addEventListener("repas-valide",this.surRepasValide),this.connexion=new me(this.hass),this.file=new xe(window.localStorage,(e,t)=>this.connexion.appeler(e,t),(e,t)=>{this.erreurFile=t}),this.enAttente=this.file.taille(),this.file.rejouer().then(()=>{this.enAttente=this.file.taille()}),this.actualiserSession(),this.connexion.abonner(()=>{this.actualiserSession(),this.requestUpdate()}).then(e=>{this.isConnected?this.desabonner=e:e()}),window.addEventListener("online",this.auRetourDuReseau),this.addEventListener("ticket-ouvert",this.surTicketOuvert),this.addEventListener("aller-liste",this.surAllerListe),this.addEventListener("manger-produit",this.surMangerProduit),this.addEventListener("consommation-enregistree",this.surConsommationEnregistree)}disconnectedCallback(){super.disconnectedCallback(),this.desabonner?.(),this.desabonner=void 0,window.removeEventListener("online",this.auRetourDuReseau),window.removeEventListener("resize",this.surRedimensionnement),this.removeEventListener("recette-ouverte",this.surRecetteOuverte),this.removeEventListener("valider-repas",this.surValiderRepas),this.removeEventListener("repas-valide",this.surRepasValide),this.removeEventListener("manger-produit",this.surMangerProduit),this.removeEventListener("consommation-enregistree",this.surConsommationEnregistree)}async actualiserSession(){try{this.session=await this.connexion.appeler("home_stock/session/current")}catch{}}async chargerFiche(e,t=!0){try{const i=await this.connexion.appeler("home_stock/lookup",{code:e});this.resultatCourant=i,t?this.naviguerVers("fiche",e):this.ecran="fiche"}catch{this.derniereFiche={nom:e,marque:null,image:null,statut:"Connexion indisponible — réessayez."},t||this.naviguerVers("scanner",null,!0)}}get lignesSessionARanger(){return this.session?.session&&"to_store"===this.session.session.state?this.session.lines.filter(e=>null===e.stored_at).map(e=>({...e,source:"session"})):[]}get lignesARanger(){return[...this.lignesSessionARanger,...this.enAttenteRangement]}get large(){return this.largeMesuree&&!this.narrow}departARisque(e){return"rangement"===this.ecran&&"rangement"!==e&&this.enAttenteRangement.length>0}armer(e,t){this.navigationArmee=e,this.parametreArme=t}demanderNavigation(e,t=null){this.departARisque(e)?this.armer(e,t):this.naviguerVers(e,t)}cheminDe(e,t){return Ht(e).param&&null==t?null:function(e,t=null){const i=Ht(e);if(!i.param)return`/${i.segment}`;if(null==t)throw new Error(`L'écran « ${e} » exige un paramètre : pathOf(${e}, …)`);return`/${i.segment}/${t}`}(e,t)}naviguerVers(e,t=null,i=!1){const s=this.cheminDe(e,t);if(null!==s){const e=`${this.route?.prefix??"/home-stock"}${s}`;i?window.history.replaceState(null,"",e):window.history.pushState(null,"",e),window.dispatchEvent(new CustomEvent("location-changed",{detail:{replace:i},bubbles:!0,composed:!0})),this.dernierChemin=s}this.ecran=e}get pastilles(){const e=this.lignesARanger.length,t="shopping"===this.session?.session?.state?this.session.totals.lines:0;return{shopping:e||t}}rendreConfirmationQuitter(){return I`
      <div class="confirmation-quitter-rangement">
        <p>
          Des articles rapportés seuls n’ont pas encore été rangés : ils seront perdus si vous quittez
          maintenant.
        </p>
        <button class="confirmer-quitter" @click=${this.confirmerNavigation}>Quitter quand même</button>
        <button class="annuler-quitter" @click=${this.annulerNavigation}>Rester ici</button>
      </div>
    `}rendreEcran(){return"fiche"===this.ecran&&this.resultatCourant?I`
        <home-stock-fiche .resultat=${this.resultatCourant}
          .mode=${"shopping"===this.session?.session?.state?"panier":"rangement"}
          .connexion=${this.connexion} .file=${this.file} @article-pret=${this.surArticlePret}>
        </home-stock-fiche>`:"panier"===this.ecran&&this.session?I`
        <home-stock-panier .donnees=${this.session} .connexion=${this.connexion}
          .file=${this.file} .enAttente=${this.enAttente} @file-changee=${this.surFileChangee}>
        </home-stock-panier>`:"rangement"===this.ecran?I`
        <home-stock-rangement .lignes=${this.lignesARanger} .connexion=${this.connexion} .file=${this.file}
          .enAttente=${this.enAttente}
          @ligne-autonome-rangee=${this.surLigneAutonomeRangee} @termine=${this.surRangementTermine}
          @file-changee=${this.surFileChangee}>
        </home-stock-rangement>`:"session"===this.ecran?I`
        <home-stock-session .donnees=${this.session} .connexion=${this.connexion}
          .file=${this.file} .enAttente=${this.enAttente}
          @session-changee=${this.surSessionChangee} @file-changee=${this.surFileChangee}
          >
        </home-stock-session>`:"catalogue"===this.ecran?I`
        <home-stock-catalogue .connexion=${this.connexion} .file=${this.file} .enAttente=${this.enAttente}
          .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-catalogue>`:"reglages"===this.ecran?I`
        <home-stock-reglages .connexion=${this.connexion} .file=${this.file} .enAttente=${this.enAttente}
          .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-reglages>`:"consommation"===this.ecran?I`
        <home-stock-consommation .connexion=${this.connexion} .file=${this.file}
          .productId=${this.produitAManger}>
        </home-stock-consommation>`:"journal"===this.ecran?I`
        <home-stock-journal .connexion=${this.connexion} .file=${this.file}
          .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-journal>`:"recettes"===this.ecran?I`
        <home-stock-recettes .connexion=${this.connexion} .file=${this.file}
          .enAttente=${this.enAttente} @file-changee=${this.surFileChangee}>
        </home-stock-recettes>`:"recette"===this.ecran&&null!==this.recetteOuverte?I`
        <home-stock-recette .connexion=${this.connexion} .file=${this.file}
          .recipeId=${this.recetteOuverte} .mealId=${this.repasDeLaRecette}
          @recette-fermee=${()=>this.demanderNavigation("recettes")}>
        </home-stock-recette>`:"validation"===this.ecran&&null!==this.repasAValider?I`
        <home-stock-validation .connexion=${this.connexion} .file=${this.file}
          .mealId=${this.repasAValider} @file-changee=${this.surFileChangee}>
        </home-stock-validation>`:"planning"===this.ecran?I`
        <home-stock-planning .connexion=${this.connexion} .file=${this.file}
          .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-planning>`:"piles"===this.ecran?I`
        <home-stock-piles .connexion=${this.connexion} .file=${this.file}
          .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-piles>`:"equipements"===this.ecran?I`
        <home-stock-equipements .connexion=${this.connexion} .file=${this.file}
          .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-equipements>`:"liste"===this.ecran?I`
        <home-stock-liste .connexion=${this.connexion} .file=${this.file}
          .enAttente=${this.enAttente} .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-liste>`:"ticket"===this.ecran?I`
        <home-stock-ticket .connexion=${this.connexion} .file=${this.file}
          .enAttente=${this.enAttente} .ticket=${this.ticketOuvert}
          .agentConfigure=${this.agentTicketConfigure} .large=${this.large}
          @file-changee=${this.surFileChangee}>
        </home-stock-ticket>`:I`
      <home-stock-scanner .session=${this.session?.session?{store:this.session.session.store}:null}
        .derniereFiche=${this.derniereFiche} .enAttente=${this.enAttente} @code-lu=${this.surCodeLu}>
      </home-stock-scanner>`}render(){return"fiche"===this.ecran?this.rendreEcran():I`
      <div class="coquille ${this.large?"large":""}">
        <hs-nav-bar class="navigation" .current=${this.ecran} .rail=${this.large}
          .badges=${this.pastilles} @famille-choisie=${this.surFamilleChoisie}></hs-nav-bar>
        <div class="colonne">
          <hs-header .current=${this.ecran} .pending=${this.enAttente} .error=${this.erreurFile}
            @retour-demande=${this.surRetour}
            @erreur-acquittee=${this.surErreurAcquittee}></hs-header>
          <main class="contenu">${this.rendreEcran()}</main>
        </div>
        <!-- EN SURCOUCHE, jamais à la place : rendreEcran() s'exécute quand
             même, donc l'écran de rangement reste MONTÉ. Le démonter jetterait
             les emplacements que l'utilisateur vient de saisir à la main
             (emplacementChoisi, un état local de home-stock-rangement) —
             perdus par le bouton qui dit « je veux continuer », le pire des
             deux pour perdre quelque chose. -->
        ${this.navigationArmee?this.rendreConfirmationQuitter():B}
      </div>`}firstUpdated(){Gt(this)}updated(e){e.has("hass")&&Gt(this)}};Yt.styles=[we,a`
    :host { display: block; height: 100%; background: var(--hs-surface-2); }
    /* Ordre du DOM : la barre AVANT la colonne, pour que le rail se pose
       naturellement à gauche en row. En column-reverse, la barre repasse en
       bas de l’écran sans quitter sa place dans le DOM — donc sans casser
       l’ordre de tabulation, et sans dvh ni :has(), absents de Chrome 100
       (la tablette de la cuisine). */
    /* position: relative — la confirmation de départ se pose EN SURCOUCHE
       par-dessus, sans démonter l'écran en dessous (voir render). */
    .coquille { position: relative; display: flex; flex-direction: column-reverse; height: 100%; }
    .coquille.large { flex-direction: row; }
    .colonne { flex: 1; display: flex; flex-direction: column; min-height: 0; }
    .contenu { flex: 1; overflow-y: auto; }
    .navigation { flex: 0 0 auto; }
    /* Une surcouche opaque, qui couvre AUSSI la barre : tant qu'un départ est
       armé, aucune autre destination n'est à un doigt de distance. Pas de
       dialog natif : Chrome 100 (la tablette de la cuisine) ne l'a pas. Pas
       d'inset non plus, les quatre côtés se disent très bien. */
    .confirmation-quitter-rangement {
      position: absolute; top: 0; right: 0; bottom: 0; left: 0; z-index: 2;
      display: flex; flex-direction: column; justify-content: center;
      gap: var(--hs-space-2);
      padding: var(--hs-space-3);
      background: var(--hs-surface); color: var(--hs-text);
    }
    .confirmation-quitter-rangement p { margin: 0; }
    .confirmer-quitter, .annuler-quitter {
      min-height: var(--hs-touch); width: 100%;
      border-radius: var(--hs-radius-s); border: none; font-size: 0.95rem;
      font-family: var(--hs-font); cursor: pointer;
    }
    /* Bordure, pas aplat : aucun texte ne tient 4,5:1 sur --hs-danger sous le
       thème HA par défaut (spec § 6.1 ter). Ce qui protège ce geste, c’est
       qu’il demande deux appuis — pas sa couleur. */
    .confirmer-quitter {
      background: var(--hs-surface); color: var(--hs-text);
      border: 2px solid var(--hs-danger);
    }
    .annuler-quitter { background: var(--hs-accent); color: var(--hs-on-accent); }
  `],e([pe({attribute:!1})],Yt.prototype,"hass",void 0),e([pe({attribute:!1})],Yt.prototype,"narrow",void 0),e([pe({attribute:!1})],Yt.prototype,"route",void 0),e([de()],Yt.prototype,"ecran",void 0),e([de()],Yt.prototype,"enAttente",void 0),e([de()],Yt.prototype,"session",void 0),e([de()],Yt.prototype,"resultatCourant",void 0),e([de()],Yt.prototype,"derniereFiche",void 0),e([de()],Yt.prototype,"enAttenteRangement",void 0),e([de()],Yt.prototype,"erreurFile",void 0),e([de()],Yt.prototype,"navigationArmee",void 0),e([de()],Yt.prototype,"produitAManger",void 0),e([de()],Yt.prototype,"largeMesuree",void 0),e([de()],Yt.prototype,"ticketOuvert",void 0),e([de()],Yt.prototype,"agentTicketConfigure",void 0),e([de()],Yt.prototype,"recetteOuverte",void 0),e([de()],Yt.prototype,"repasDeLaRecette",void 0),e([de()],Yt.prototype,"repasAValider",void 0),Yt=e([ce("home-stock-panel")],Yt);export{Yt as PanneauGardeManger};
