function e(e,t,i,r){var s,n=arguments.length,o=n<3?t:null===r?r=Object.getOwnPropertyDescriptor(t,i):r;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)o=Reflect.decorate(e,t,i,r);else for(var a=e.length-1;a>=0;a--)(s=e[a])&&(o=(n<3?s(o):n>3?s(t,i,o):s(t,i))||o);return n>3&&o&&Object.defineProperty(t,i,o),o}"function"==typeof SuppressedError&&SuppressedError;
/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const t=globalThis,i=t.ShadowRoot&&(void 0===t.ShadyCSS||t.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,r=Symbol(),s=new WeakMap;let n=class{constructor(e,t,i){if(this._$cssResult$=!0,i!==r)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o;const t=this.t;if(i&&void 0===e){const i=void 0!==t&&1===t.length;i&&(e=s.get(t)),void 0===e&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&s.set(t,e))}return e}toString(){return this.cssText}};const o=(e,...t)=>{const i=1===e.length?e[0]:t.reduce((t,i,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if("number"==typeof e)return e;throw Error("Value passed to 'css' function must be a 'css' function result: "+e+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+e[r+1],e[0]);return new n(i,e,r)},a=i?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t="";for(const i of e.cssRules)t+=i.cssText;return(e=>new n("string"==typeof e?e:e+"",void 0,r))(t)})(e):e,{is:l,defineProperty:c,getOwnPropertyDescriptor:u,getOwnPropertyNames:p,getOwnPropertySymbols:d,getPrototypeOf:h}=Object,m=globalThis,g=m.trustedTypes,f=g?g.emptyScript:"",b=m.reactiveElementPolyfillSupport,v=(e,t)=>e,x={toAttribute(e,t){switch(t){case Boolean:e=e?f:null;break;case Object:case Array:e=null==e?e:JSON.stringify(e)}return e},fromAttribute(e,t){let i=e;switch(t){case Boolean:i=null!==e;break;case Number:i=null===e?null:Number(e);break;case Object:case Array:try{i=JSON.parse(e)}catch(e){i=null}}return i}},y=(e,t)=>!l(e,t),$={attribute:!0,type:String,converter:x,reflect:!1,useDefault:!1,hasChanged:y};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */Symbol.metadata??=Symbol("metadata"),m.litPropertyMetadata??=new WeakMap;let _=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=$){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){const i=Symbol(),r=this.getPropertyDescriptor(e,i,t);void 0!==r&&c(this.prototype,e,r)}}static getPropertyDescriptor(e,t,i){const{get:r,set:s}=u(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){const n=r?.call(this);s?.call(this,t),this.requestUpdate(e,n,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??$}static _$Ei(){if(this.hasOwnProperty(v("elementProperties")))return;const e=h(this);e.finalize(),void 0!==e.l&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(v("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(v("properties"))){const e=this.properties,t=[...p(e),...d(e)];for(const i of t)this.createProperty(i,e[i])}const e=this[Symbol.metadata];if(null!==e){const t=litPropertyMetadata.get(e);if(void 0!==t)for(const[e,i]of t)this.elementProperties.set(e,i)}this._$Eh=new Map;for(const[e,t]of this.elementProperties){const i=this._$Eu(e,t);void 0!==i&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){const t=[];if(Array.isArray(e)){const i=new Set(e.flat(1/0).reverse());for(const e of i)t.unshift(a(e))}else void 0!==e&&t.push(a(e));return t}static _$Eu(e,t){const i=t.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof e?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),void 0!==this.renderRoot&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){const e=new Map,t=this.constructor.elementProperties;for(const i of t.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){const e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((e,r)=>{if(i)e.adoptedStyleSheets=r.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(const i of r){const r=document.createElement("style"),s=t.litNonce;void 0!==s&&r.setAttribute("nonce",s),r.textContent=i.cssText,e.appendChild(r)}})(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,i){this._$AK(e,i)}_$ET(e,t){const i=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,i);if(void 0!==r&&!0===i.reflect){const s=(void 0!==i.converter?.toAttribute?i.converter:x).toAttribute(t,i.type);this._$Em=e,null==s?this.removeAttribute(r):this.setAttribute(r,s),this._$Em=null}}_$AK(e,t){const i=this.constructor,r=i._$Eh.get(e);if(void 0!==r&&this._$Em!==r){const e=i.getPropertyOptions(r),s="function"==typeof e.converter?{fromAttribute:e.converter}:void 0!==e.converter?.fromAttribute?e.converter:x;this._$Em=r;const n=s.fromAttribute(t,e.type);this[r]=n??this._$Ej?.get(r)??n,this._$Em=null}}requestUpdate(e,t,i,r=!1,s){if(void 0!==e){const n=this.constructor;if(!1===r&&(s=this[e]),i??=n.getPropertyOptions(e),!((i.hasChanged??y)(s,t)||i.useDefault&&i.reflect&&s===this._$Ej?.get(e)&&!this.hasAttribute(n._$Eu(e,i))))return;this.C(e,t,i)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:i,reflect:r,wrapped:s},n){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,n??t??this[e]),!0!==s||void 0!==n)||(this._$AL.has(e)||(this.hasUpdated||i||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}const e=this.scheduleUpdate();return null!=e&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}const e=this.constructor.elementProperties;if(e.size>0)for(const[t,i]of e){const{wrapped:e}=i,r=this[t];!0!==e||this._$AL.has(t)||void 0===r||this.C(t,void 0,i,r)}}let e=!1;const t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};_.elementStyles=[],_.shadowRootOptions={mode:"open"},_[v("elementProperties")]=new Map,_[v("finalized")]=new Map,b?.({ReactiveElement:_}),(m.reactiveElementVersions??=[]).push("2.1.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const k=globalThis,w=e=>e,A=k.trustedTypes,C=A?A.createPolicy("lit-html",{createHTML:e=>e}):void 0,E="$lit$",q=`lit$${Math.random().toFixed(9).slice(2)}$`,S="?"+q,P=`<${S}>`,z=document,j=()=>z.createComment(""),L=e=>null===e||"object"!=typeof e&&"function"!=typeof e,R=Array.isArray,M="[ \t\n\f\r]",F=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,O=/-->/g,N=/>/g,T=RegExp(`>|${M}(?:([^\\s"'>=/]+)(${M}*=${M}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),I=/'/g,D=/"/g,U=/^(?:script|style|textarea|title)$/i,B=(e=>(t,...i)=>({_$litType$:e,strings:t,values:i}))(1),V=Symbol.for("lit-noChange"),H=Symbol.for("lit-nothing"),J=new WeakMap,Q=z.createTreeWalker(z,129);function W(e,t){if(!R(e)||!e.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==C?C.createHTML(t):t}const Y=(e,t)=>{const i=e.length-1,r=[];let s,n=2===t?"<svg>":3===t?"<math>":"",o=F;for(let t=0;t<i;t++){const i=e[t];let a,l,c=-1,u=0;for(;u<i.length&&(o.lastIndex=u,l=o.exec(i),null!==l);)u=o.lastIndex,o===F?"!--"===l[1]?o=O:void 0!==l[1]?o=N:void 0!==l[2]?(U.test(l[2])&&(s=RegExp("</"+l[2],"g")),o=T):void 0!==l[3]&&(o=T):o===T?">"===l[0]?(o=s??F,c=-1):void 0===l[1]?c=-2:(c=o.lastIndex-l[2].length,a=l[1],o=void 0===l[3]?T:'"'===l[3]?D:I):o===D||o===I?o=T:o===O||o===N?o=F:(o=T,s=void 0);const p=o===T&&e[t+1].startsWith("/>")?" ":"";n+=o===F?i+P:c>=0?(r.push(a),i.slice(0,c)+E+i.slice(c)+q+p):i+q+(-2===c?t:p)}return[W(e,n+(e[i]||"<?>")+(2===t?"</svg>":3===t?"</math>":"")),r]};class G{constructor({strings:e,_$litType$:t},i){let r;this.parts=[];let s=0,n=0;const o=e.length-1,a=this.parts,[l,c]=Y(e,t);if(this.el=G.createElement(l,i),Q.currentNode=this.el.content,2===t||3===t){const e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;null!==(r=Q.nextNode())&&a.length<o;){if(1===r.nodeType){if(r.hasAttributes())for(const e of r.getAttributeNames())if(e.endsWith(E)){const t=c[n++],i=r.getAttribute(e).split(q),o=/([.?@])?(.*)/.exec(t);a.push({type:1,index:s,name:o[2],strings:i,ctor:"."===o[1]?te:"?"===o[1]?ie:"@"===o[1]?re:ee}),r.removeAttribute(e)}else e.startsWith(q)&&(a.push({type:6,index:s}),r.removeAttribute(e));if(U.test(r.tagName)){const e=r.textContent.split(q),t=e.length-1;if(t>0){r.textContent=A?A.emptyScript:"";for(let i=0;i<t;i++)r.append(e[i],j()),Q.nextNode(),a.push({type:2,index:++s});r.append(e[t],j())}}}else if(8===r.nodeType)if(r.data===S)a.push({type:2,index:s});else{let e=-1;for(;-1!==(e=r.data.indexOf(q,e+1));)a.push({type:7,index:s}),e+=q.length-1}s++}}static createElement(e,t){const i=z.createElement("template");return i.innerHTML=e,i}}function Z(e,t,i=e,r){if(t===V)return t;let s=void 0!==r?i._$Co?.[r]:i._$Cl;const n=L(t)?void 0:t._$litDirective$;return s?.constructor!==n&&(s?._$AO?.(!1),void 0===n?s=void 0:(s=new n(e),s._$AT(e,i,r)),void 0!==r?(i._$Co??=[])[r]=s:i._$Cl=s),void 0!==s&&(t=Z(e,s._$AS(e,t.values),s,r)),t}class K{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){const{el:{content:t},parts:i}=this._$AD,r=(e?.creationScope??z).importNode(t,!0);Q.currentNode=r;let s=Q.nextNode(),n=0,o=0,a=i[0];for(;void 0!==a;){if(n===a.index){let t;2===a.type?t=new X(s,s.nextSibling,this,e):1===a.type?t=new a.ctor(s,a.name,a.strings,this,e):6===a.type&&(t=new se(s,this,e)),this._$AV.push(t),a=i[++o]}n!==a?.index&&(s=Q.nextNode(),n++)}return Q.currentNode=z,r}p(e){let t=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(e,i,t),t+=i.strings.length-2):i._$AI(e[t])),t++}}class X{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,i,r){this.type=2,this._$AH=H,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=i,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode;const t=this._$AM;return void 0!==t&&11===e?.nodeType&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=Z(this,e,t),L(e)?e===H||null==e||""===e?(this._$AH!==H&&this._$AR(),this._$AH=H):e!==this._$AH&&e!==V&&this._(e):void 0!==e._$litType$?this.$(e):void 0!==e.nodeType?this.T(e):(e=>R(e)||"function"==typeof e?.[Symbol.iterator])(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==H&&L(this._$AH)?this._$AA.nextSibling.data=e:this.T(z.createTextNode(e)),this._$AH=e}$(e){const{values:t,_$litType$:i}=e,r="number"==typeof i?this._$AC(e):(void 0===i.el&&(i.el=G.createElement(W(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===r)this._$AH.p(t);else{const e=new K(r,this),i=e.u(this.options);e.p(t),this.T(i),this._$AH=e}}_$AC(e){let t=J.get(e.strings);return void 0===t&&J.set(e.strings,t=new G(e)),t}k(e){R(this._$AH)||(this._$AH=[],this._$AR());const t=this._$AH;let i,r=0;for(const s of e)r===t.length?t.push(i=new X(this.O(j()),this.O(j()),this,this.options)):i=t[r],i._$AI(s),r++;r<t.length&&(this._$AR(i&&i._$AB.nextSibling,r),t.length=r)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){const t=w(e).nextSibling;w(e).remove(),e=t}}setConnected(e){void 0===this._$AM&&(this._$Cv=e,this._$AP?.(e))}}class ee{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,i,r,s){this.type=1,this._$AH=H,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=s,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=H}_$AI(e,t=this,i,r){const s=this.strings;let n=!1;if(void 0===s)e=Z(this,e,t,0),n=!L(e)||e!==this._$AH&&e!==V,n&&(this._$AH=e);else{const r=e;let o,a;for(e=s[0],o=0;o<s.length-1;o++)a=Z(this,r[i+o],t,o),a===V&&(a=this._$AH[o]),n||=!L(a)||a!==this._$AH[o],a===H?e=H:e!==H&&(e+=(a??"")+s[o+1]),this._$AH[o]=a}n&&!r&&this.j(e)}j(e){e===H?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}}class te extends ee{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===H?void 0:e}}class ie extends ee{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==H)}}class re extends ee{constructor(e,t,i,r,s){super(e,t,i,r,s),this.type=5}_$AI(e,t=this){if((e=Z(this,e,t,0)??H)===V)return;const i=this._$AH,r=e===H&&i!==H||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,s=e!==H&&(i===H||r);r&&this.element.removeEventListener(this.name,this,i),s&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}}class se{constructor(e,t,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){Z(this,e)}}const ne=k.litHtmlPolyfillSupport;ne?.(G,X),(k.litHtmlVersions??=[]).push("3.3.3");const oe=globalThis;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */class ae extends _{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){const t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=((e,t,i)=>{const r=i?.renderBefore??t;let s=r._$litPart$;if(void 0===s){const e=i?.renderBefore??null;r._$litPart$=s=new X(t.insertBefore(j(),e),e,void 0,i??{})}return s._$AI(e),s})(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return V}}ae._$litElement$=!0,ae.finalized=!0,oe.litElementHydrateSupport?.({LitElement:ae});const le=oe.litElementPolyfillSupport;le?.({LitElement:ae}),(oe.litElementVersions??=[]).push("4.2.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const ce=e=>(t,i)=>{void 0!==i?i.addInitializer(()=>{customElements.define(e,t)}):customElements.define(e,t)},ue={attribute:!0,type:String,converter:x,reflect:!1,hasChanged:y},pe=(e=ue,t,i)=>{const{kind:r,metadata:s}=i;let n=globalThis.litPropertyMetadata.get(s);if(void 0===n&&globalThis.litPropertyMetadata.set(s,n=new Map),"setter"===r&&((e=Object.create(e)).wrapped=!0),n.set(i.name,e),"accessor"===r){const{name:r}=i;return{set(i){const s=t.get.call(this);t.set.call(this,i),this.requestUpdate(r,s,e,!0,i)},init(t){return void 0!==t&&this.C(r,void 0,e,t),t}}}if("setter"===r){const{name:r}=i;return function(i){const s=this[r];t.call(this,i),this.requestUpdate(r,s,e,!0,i)}}throw Error("Unsupported decorator location: "+r)};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function de(e){return(t,i)=>"object"==typeof i?pe(e,t,i):((e,t,i)=>{const r=t.hasOwnProperty(i);return t.constructor.createProperty(i,e),r?Object.getOwnPropertyDescriptor(t,i):void 0})(e,t,i)}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function he(e){return de({...e,state:!0,attribute:!1})}class me{constructor(e){this.hass=e}appeler(e,t={}){return this.hass.connection.sendMessagePromise({type:e,...t})}abonner(e){return this.hass.connection.subscribeMessage(e,{type:"home_stock/subscribe"})}appelerService(e,t,i={}){return this.hass.callService(e,t,i)}async televerserMedia(e,t){const i=new FormData;i.append("media_content_id",t),i.append("file",e);const r=this.hass.auth?.data?.access_token,s=await fetch("/api/media_source/local_source/upload",{method:"POST",body:i,headers:r?{authorization:`Bearer ${r}`}:{}});if(!s.ok)throw new Error(String(s.status));return(await s.json()).media_content_id}}function ge(e){return!!e&&"object"==typeof e&&"string"==typeof e.code&&"string"==typeof e.message}const fe=new Set(["not_loaded","invalid_field","invalid_value","not_found","already_exists","conversion_refused","shopping_refused","insufficient_stock"]);function be(e){return fe.has(e.code)?e.message:"Une action a été refusée et n’a pas pu être envoyée."}const ve="home_stock.file";class xe{constructor(e,t,i){this.stockage=e,this.envoyer=t,this.surRefus=i,this.actions=[],this.enVol=null;try{this.actions=JSON.parse(this.stockage.getItem(ve)??"[]")}catch{this.actions=[]}}ajouter(e,t){const i={...t};let r;"string"!=typeof i.idempotency_key&&(i.idempotency_key=crypto.randomUUID());const s=new Promise(e=>{r=e});let n;const o=new Promise(e=>{n=e});return this.actions.push({type:e,charge:i,resoudre:r,repondre:n}),this.ecrire(),{cle:i.idempotency_key,sort:s,reponse:o}}taille(){return this.actions.length}async rejouer(){const e=this.enVol,t=(async()=>{e&&await e.catch(()=>{}),await this.boucle()})();this.enVol=t;try{await t}finally{this.enVol===t&&(this.enVol=null)}}async boucle(){for(;this.actions.length;){const e=this.actions[0];let t;try{t=await this.envoyer(e.type,e.charge)}catch(t){if(ge(t)){this.actions.shift(),this.ecrire(),e.resoudre?.("refusee"),e.repondre?.(void 0),this.surRefus?.(e,be(t));continue}for(const e of this.actions)e.resoudre?.("en-attente"),e.repondre?.(void 0),e.resoudre=void 0,e.repondre=void 0;return}this.actions.shift(),this.ecrire(),e.resoudre?.("envoyee"),e.repondre?.(t)}}ecrire(){this.stockage.setItem(ve,JSON.stringify(this.actions.map(({type:e,charge:t})=>({type:e,charge:t}))))}}class ye{constructor(e){this.fenetre=e,this.voie="companion"}disponible(){return Boolean(this.fenetre?.externalApp?.externalBus||this.fenetre?.webkit?.messageHandlers?.externalBus)}lire(){return new Promise(e=>{const t=this.fenetre.externalBus;let i=!1;const r=r=>{i||(i=!0,clearTimeout(s),this.fenetre.externalBus=t,e(r))},s=setTimeout(()=>r(null),6e4);this.fenetre.externalBus=e=>{const t="string"==typeof e?JSON.parse(e):e;return"bar_code/scan_result"===t.command?(this.envoyer({type:"bar_code/close"}),r(String(t.payload.rawValue))):"bar_code/aborted"!==t.command&&"bar_code/close"!==t.command||r(null),!0},this.envoyer({type:"bar_code/scan",payload:{title:"Scanner un article",description:"Visez le code-barres",alternative_option_label:"Saisir le code"}})})}envoyer(e){const t=JSON.stringify(e);this.fenetre.externalApp?.externalBus?this.fenetre.externalApp.externalBus(t):this.fenetre.webkit.messageHandlers.externalBus.postMessage(e)}}const $e=["ean_13","ean_8","upc_a","upc_e","code_128"];class _e{constructor(e){this.fenetre=e,this.voie="navigateur"}disponible(){return Boolean(this.fenetre?.BarcodeDetector&&this.fenetre?.navigator?.mediaDevices)}async lire(){try{const e=new this.fenetre.BarcodeDetector({formats:$e});this.flux=await this.fenetre.navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}});const t=this.fenetre.document.createElement("video");t.srcObject=this.flux,t.setAttribute("playsinline","true"),t.setAttribute("muted","true"),t.style.cssText="position:fixed;inset:0;width:100%;height:100%;object-fit:cover;z-index:2147483647;background:#000;",this.fenetre.document.body.appendChild(t),this.video=t,await t.play();for(let i=0;i<300;i+=1){const i=await e.detect(t);if(i.length)return String(i[0].rawValue);await new Promise(e=>this.fenetre.requestAnimationFrame(e))}return null}finally{this.arreter()}}arreter(){this.flux?.getTracks().forEach(e=>e.stop()),this.flux=void 0,this.video?.remove(),this.video=void 0}}class ke{constructor(){this.voie="clavier"}disponible(){return!0}async lire(){return null}}const we={label:"nom",brand:"marque",net_quantity:"poids net",image:"image",kcal_per_base_unit:"calories",proteins:"protéines",carbohydrates:"glucides",sugars:"sucres",added_sugars:"sucres ajoutés",fat:"matières grasses",saturated_fat:"graisses saturées",fiber:"fibres",salt:"sel",nutriscore:"Nutri-Score",nova:"classification NOVA",ecoscore:"Éco-score",allergens:"allergènes",traces:"traces",additives:"additifs",off_labels:"labels",off_raw:"réponse Open Food Facts"};function Ae(e,t,i){return null==e?"":"piece"===t?e.toFixed(2).replace(".",","):"g"===t||"ml"===t?null===i||i<=0?"":(e*i).toFixed(2).replace(".",","):""}function Ce(e,t,i){const r=Number.parseFloat(e.trim().replace(",","."));return Number.isFinite(r)?"piece"===t?r:"g"===t||"ml"===t?null===i||i<=0?null:r/i:null:null}function Ee(e){return e.known?e.article?.net_quantity??null:e.off?.net_quantity??null}function qe(e){return e&&"object"==typeof e&&"message"in e&&"string"==typeof e.message?e.message:"Une erreur est survenue."}let Se=class extends ae{constructor(){super(...arguments),this.mode="rangement",this.productChoisi=null,this.nomNouveauProduit="",this.uniteNouveauProduit="piece",this.prixSaisi=null,this.poidsPaquet="",this.quantitePaquets=1,this.produitsBaseUnit={},this.rapportConversion=null,this.erreurConversion=null,this.erreurAction=null,this.erreurUnites=null,this.enCours=!1}willUpdate(e){if(e.has("resultat")&&this.resultat){this.productChoisi=this.resultat.preselected_product_id,this.nomNouveauProduit=this.resultat.off?.generic_name??"",this.uniteNouveauProduit=this.resultat.off?.net_unit??"piece";const e=Ee(this.resultat);this.poidsPaquet=null!==e?String(e):"",this.prixSaisi=null,this.quantitePaquets=1,this.rapportConversion=null,this.erreurConversion=null,this.erreurAction=null,this.erreurUnites=null,this.produitsBaseUnit={}}}updated(e){e.has("resultat")&&this.resultat&&!this.resultat.known&&this.resultat.candidates.length&&this.connexion&&this.chargerUnitesProduits()}async chargerUnitesProduits(){this.erreurUnites=null;try{const e=await this.connexion.appeler("home_stock/products/list"),t={};for(const i of e.products)t[i.id]=i.base_unit;this.produitsBaseUnit=t}catch{this.erreurUnites="Impossible de récupérer les informations du produit. Vérifiez la connexion."}}uniteConnue(){return this.resultat.known?this.resultat.product?.base_unit??null:"new"===this.productChoisi?this.uniteNouveauProduit:"number"==typeof this.productChoisi?this.produitsBaseUnit[this.productChoisi]??null:null}get poidsEffectif(){return function(e){const t=Number.parseFloat(e.trim().replace(",","."));return Number.isFinite(t)&&t>0?t:null}(this.poidsPaquet)}get valeurPrix(){if(null!==this.prixSaisi)return this.prixSaisi;const e=this.uniteConnue(),t="piece"===e?null:this.poidsEffectif;return Ae(this.resultat.price?.price_per_base_unit,e,t)}get raisonBlocage(){if(!this.resultat)return null;if(!this.resultat.known){if(!this.connexion)return"Connexion indisponible.";if(null===this.productChoisi)return"Choisissez un produit.";if("new"===this.productChoisi&&!this.nomNouveauProduit.trim())return"Donnez un nom au nouveau produit."}const e=this.uniteConnue();return null===e?this.erreurUnites??"Chargement des informations du produit…":"g"!==e&&"ml"!==e||null!==this.poidsEffectif?null:"Indiquez le poids du paquet pour calculer le prix."}get peutValider(){return!this.enCours&&null===this.raisonBlocage}enregistrerPoidsCorrige(e,t){const i={article_id:e,fields:{net_quantity:t}};this.file?this.file.ajouter("home_stock/article/update",i):this.connexion&&this.connexion.appeler("home_stock/article/update",i).catch(()=>{})}async valider(){if(this.peutValider){this.enCours=!0,this.erreurAction=null;try{const e=this.uniteConnue(),t="piece"===e?null:this.poidsEffectif,i=null===Ee(this.resultat);let r,s=[];if(this.resultat.known)r=this.resultat.article.id,null!==t&&i&&this.enregistrerPoidsCorrige(r,t);else{const e={code:this.resultat.code};this.resultat.off_raw&&(e.off=this.resultat.off_raw),this.resultat.off_source&&(e.off_source=this.resultat.off_source),"new"===this.productChoisi?e.new_product={name:this.nomNouveauProduit.trim(),base_unit:this.uniteNouveauProduit}:e.product_id=this.productChoisi,null!==t&&i&&(e.fields={net_quantity:t});const n=await this.connexion.appeler("home_stock/article/create",e);r=n.article_id,s=n.off_dropped_fields??[]}const n={articleId:r,quantite:"piece"===e?this.quantitePaquets:t*this.quantitePaquets,prixUnitaire:Ce(this.valeurPrix,e,t),mode:this.mode,offDroppedFields:s};this.dispatchEvent(new CustomEvent("article-pret",{detail:n,bubbles:!0,composed:!0}))}catch(e){this.erreurAction=qe(e)}finally{this.enCours=!1}}}mangerProduit(e){this.dispatchEvent(new CustomEvent("manger-produit",{detail:{product_id:e},bubbles:!0,composed:!0}))}async voirEffetConversion(){const e=this.resultat.conversion_offer;if(e&&this.connexion){this.erreurConversion=null;try{this.rapportConversion=await this.connexion.appeler("home_stock/product/convert_unit",{product_id:e.product_id,to_unit:e.to_unit,reference_quantity:e.reference_quantity,dry_run:!0})}catch(e){this.erreurConversion=qe(e)}}}async appliquerConversion(){const e=this.resultat.conversion_offer;if(e&&this.connexion&&this.rapportConversion){this.erreurConversion=null;try{this.rapportConversion=await this.connexion.appeler("home_stock/product/convert_unit",{product_id:e.product_id,to_unit:e.to_unit,reference_quantity:e.reference_quantity,dry_run:!1})}catch(e){this.erreurConversion=qe(e)}}}rendreRattachement(){return this.resultat.known?H:B`
      <section class="rattachement">
        ${this.resultat.candidates.map(e=>B`
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
        ${"new"===this.productChoisi?B`
          <div class="nouveau-produit">
            <input class="nom-nouveau" placeholder="Nom du produit" .value=${this.nomNouveauProduit}
              @input=${e=>{this.nomNouveauProduit=e.target.value}} />
            <select class="unite-nouveau" .value=${this.uniteNouveauProduit}
              @change=${e=>{this.uniteNouveauProduit=e.target.value}}>
              <option value="g">grammes</option>
              <option value="ml">millilitres</option>
              <option value="piece">à la pièce</option>
            </select>
          </div>`:H}
        ${this.erreurUnites?B`
          <p class="erreur-unite">${this.erreurUnites}</p>
          <button class="reessayer-unite" @click=${()=>{this.chargerUnitesProduits()}}>
            Réessayer
          </button>`:H}
      </section>
    `}rendreAlerteOff(){const e=this.resultat;return e.known||e.off?H:e.throttled?B`<p class="alerte-off">Open Food Facts limite les requêtes en ce moment — réessayez
        dans un instant plutôt que de créer un doublon.</p>`:e.timed_out?B`<p class="alerte-off">Open Food Facts n'a pas répondu à temps — le produit existe
        peut-être déjà là-bas, réessayez avant de créer un doublon.</p>`:H}rendreConversion(){const e=this.resultat.conversion_offer;return e?B`
      <section class="conversion-offre">
        <p>Passer de pièce à ${e.to_unit} — 1 unité = ${e.reference_quantity} ${e.to_unit}</p>
        ${this.rapportConversion?B`
          <p class="rapport-conversion">
            ${this.rapportConversion.articles} article(s), ${this.rapportConversion.batches} lot(s),
            ${this.rapportConversion.movements} mouvement(s) concernés
            ${this.rapportConversion.articles_using_reference.length?B`
              — dont ${this.rapportConversion.articles_using_reference.length} article(s) qui seront
              re-pesé(s) avec un poids de référence estimé, faute de poids propre.`:"."}
          </p>
          ${this.rapportConversion.applied?B`<p class="conversion-appliquee">Conversion appliquée.</p>`:B`<button class="appliquer-conversion" @click=${this.appliquerConversion}>
                Appliquer la conversion
              </button>`}
        `:B`<button class="voir-effet" @click=${this.voirEffetConversion}>
            Voir l'effet du changement d'unité
          </button>`}
        ${this.erreurConversion?B`<p class="erreur-conversion">${this.erreurConversion}</p>`:H}
      </section>
    `:H}render(){if(!this.resultat)return H;const e=this.resultat,t=e.off?.label??e.article?.label??e.product?.name??"Article",i=e.off?.brand??e.article?.brand??null,r=e.article?.net_quantity??e.off?.net_quantity??null,s=e.product?.base_unit??e.off?.net_unit??"",n=e.off?.image??e.article?.image??null,o=e.off?.nutriscore??e.article?.nutriscore??null,a=function(e){const t=e.off?.nutrition_per_100?.kcal;if(null!=t)return t;const i=e.article?.kcal_per_base_unit,r=e.product?.base_unit;return null==i||"g"!==r&&"ml"!==r?null:100*i}(e),l=this.uniteConnue(),c="piece"===l?null:this.poidsEffectif,u="g"===l||"ml"===l?Ce(this.valeurPrix,l,c):null,p=null!=u?1e3*u:null,d="ml"===l?"L":"kg";return B`
      <section class="entete">
        ${n?B`<img class="image" src=${n} alt="" />`:H}
        <h2 class="nom">${t}</h2>
        ${i?B`<p class="marque">${i}</p>`:H}
        ${r?B`<p class="poids">${r} ${s}</p>`:H}
        ${o?B`<p class="nutriscore">Nutri-Score ${o.toUpperCase()}</p>`:H}
        ${null!=a?B`<p class="kcal">${Math.round(a)} kcal / 100 g</p>`:H}
      </section>

      ${this.rendreAlerteOff()}
      ${this.rendreRattachement()}

      <section class="prix">
        <p class="prix-provenance">${h=e.price,h&&null!=h.price_per_base_unit&&h.source?"store"===h.source?h.store?`dernier prix ${h.store}`:"dernier prix en magasin":"open_prices"===h.source?"Open Prices":"dernier prix connu":"Aucun prix connu"}</p>
        ${"g"!==l&&"ml"!==l||null!==Ee(e)?H:B`
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
        ${null!=p?B`
          <p class="prix-detail">soit ${p.toFixed(2).replace(".",",")} €/${d}</p>
        `:H}
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

      ${this.raisonBlocage?B`<p class="motif-blocage">${this.raisonBlocage}</p>`:H}
      ${this.erreurAction?B`<p class="erreur-action">${this.erreurAction}</p>`:H}

      <button class="action-principale" ?disabled=${!this.peutValider} @click=${this.valider}>
        ${"panier"===this.mode?"Au panier":"Ranger"}
      </button>
      ${null!=e.product?.id?B`
        <button type="button" class="manger" @click=${()=>this.mangerProduit(e.product.id)}>
          Manger
        </button>
      `:H}
    `;var h}};Se.styles=o`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .image { max-width: 100%; max-height: 160px; display: block; margin: 0 auto 8px; border-radius: 8px; }
    .nom { margin: 0; font-size: 1.2rem; }
    .marque, .poids, .nutriscore, .kcal { margin: 2px 0; color: var(--secondary-text-color); }
    .alerte-off {
      background: var(--warning-color, #fff3cd); color: var(--primary-text-color);
      padding: 8px; border-radius: 8px; margin: 8px 0;
    }
    .candidat { display: flex; align-items: center; gap: 8px; min-height: 48px; }
    .candidat input { width: 22px; height: 22px; }
    .nom-nouveau, .prix-champ, .poids-champ, .unite-nouveau {
      min-height: 48px; font-size: 1rem; padding: 4px 8px; box-sizing: border-box; width: 100%;
    }
    .prix { margin: 12px 0; }
    .prix-provenance { color: var(--secondary-text-color); margin: 0 0 4px; }
    .prix-detail { color: var(--secondary-text-color); font-size: 0.85rem; }
    .poids-label, .prix-label { display: block; margin: 8px 0; }
    .quantite { display: flex; align-items: center; gap: 12px; margin: 12px 0; }
    .quantite button {
      min-width: 62px; min-height: 62px; font-size: 1.5rem; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .valeur-quantite { min-width: 32px; text-align: center; font-size: 1.2rem; }
    .conversion-offre { margin: 12px 0; padding: 8px; border-radius: 8px; background: var(--secondary-background-color); }
    .motif-blocage, .erreur-action, .erreur-conversion, .erreur-unite {
      color: var(--error-color, #b3261e); font-size: 0.9rem;
    }
    .reessayer-unite {
      min-height: 48px; width: 100%; margin-top: 4px; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .action-principale {
      display: block; width: 100%; min-height: 62px; font-size: 1.2rem; border-radius: 12px;
      border: none; background: var(--primary-color); color: var(--text-primary-color, #fff);
      margin-top: 12px;
    }
    .action-principale:disabled { opacity: 0.5; }
    .manger {
      display: block; width: 100%; min-height: 48px; font-size: 1rem; border-radius: 8px;
      border: none; background: var(--secondary-background-color); color: var(--primary-text-color);
      margin-top: 8px;
    }
    button.voir-effet, button.appliquer-conversion {
      min-height: 48px; width: 100%; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
  `,e([de({attribute:!1})],Se.prototype,"resultat",void 0),e([de({attribute:!1})],Se.prototype,"mode",void 0),e([de({attribute:!1})],Se.prototype,"connexion",void 0),e([de({attribute:!1})],Se.prototype,"file",void 0),e([he()],Se.prototype,"productChoisi",void 0),e([he()],Se.prototype,"nomNouveauProduit",void 0),e([he()],Se.prototype,"uniteNouveauProduit",void 0),e([he()],Se.prototype,"prixSaisi",void 0),e([he()],Se.prototype,"poidsPaquet",void 0),e([he()],Se.prototype,"quantitePaquets",void 0),e([he()],Se.prototype,"produitsBaseUnit",void 0),e([he()],Se.prototype,"rapportConversion",void 0),e([he()],Se.prototype,"erreurConversion",void 0),e([he()],Se.prototype,"erreurAction",void 0),e([he()],Se.prototype,"erreurUnites",void 0),e([he()],Se.prototype,"enCours",void 0),Se=e([ce("home-stock-fiche")],Se);let Pe=class extends ae{constructor(){super(...arguments),this.fenetre=window,this.derniereFiche=null,this.session=null,this.enAttente=0,this.saisieOuverte=!1,this.codeSaisi="",this.enCours=!1,this.erreur=null}obtenirScanner(){return this.scanner||(this.scanner=function(e){const t=new ye(e);if(t.disponible())return t;const i=new _e(e);return i.disponible()?i:new ke}(this.fenetre??window)),this.scanner}async lancerScan(){const e=this.obtenirScanner();if("clavier"!==e.voie){this.enCours=!0,this.erreur=null;try{const t=await e.lire();t&&this.emettreCode(t)}catch{this.erreur="La caméra n’a pas pu être utilisée. Essayez la saisie manuelle."}finally{this.enCours=!1}}else this.saisieOuverte=!0}emettreCode(e){this.saisieOuverte=!1,this.codeSaisi="",this.dispatchEvent(new CustomEvent("code-lu",{detail:{code:e},bubbles:!0,composed:!0}))}validerSaisie(){const e=this.codeSaisi.trim();e&&this.emettreCode(e)}render(){return B`
      ${this.session?B`
        <p class="session-banniere">
          Session ouverte${this.session.store?` — ${this.session.store}`:""}
        </p>`:H}

      <button class="bouton-scan" ?disabled=${this.enCours} @click=${this.lancerScan}>
        ${this.enCours?"Scan en cours…":"Scanner un article"}
      </button>

      ${this.erreur?B`<p class="erreur">${this.erreur}</p>`:H}

      ${this.derniereFiche?B`
        <section class="derniere-fiche">
          ${this.derniereFiche.image?B`<img src=${this.derniereFiche.image} alt="" />`:H}
          <p class="derniere-fiche-nom">
            ${this.derniereFiche.nom}${this.derniereFiche.marque?` — ${this.derniereFiche.marque}`:""}
          </p>
          <p class="derniere-fiche-statut">${this.derniereFiche.statut}</p>
          ${void 0!==this.derniereFiche.quantite?B`
            <p class="derniere-fiche-quantite">
              Quantité : ${this.derniereFiche.quantite}${null!=this.derniereFiche.prixTotal?` — ${this.derniereFiche.prixTotal.toFixed(2).replace(".",",")} €`:""}
            </p>`:H}
          ${this.derniereFiche.ignores?.length?B`
            <p class="derniere-fiche-ignores">
              Ignoré par Open Food Facts : ${e=this.derniereFiche.ignores,e.map(e=>we[e]??e).join(", ")}
            </p>`:H}
        </section>`:H}

      ${this.enAttente>0?B`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:H}

      <button class="bouton-saisie" @click=${()=>{this.saisieOuverte=!this.saisieOuverte}}>
        Saisir le code
      </button>

      ${this.saisieOuverte?B`
        <div class="saisie-manuelle">
          <input class="champ-code" inputmode="numeric" placeholder="Code-barres" .value=${this.codeSaisi}
            @input=${e=>{this.codeSaisi=e.target.value}}
            @keydown=${e=>{"Enter"===e.key&&this.validerSaisie()}} />
          <button class="valider-saisie" @click=${this.validerSaisie}>Valider</button>
        </div>`:H}
    `;var e}};function ze(e){return`${e.toFixed(2).replace(".",",")} €`}Pe.styles=o`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .session-banniere {
      background: var(--secondary-background-color); padding: 8px 12px; border-radius: 8px;
      margin: 0 0 12px; text-align: center;
    }
    .bouton-scan {
      display: block; width: 100%; min-height: 96px; font-size: 1.4rem; font-weight: 600;
      border-radius: 16px; border: none; background: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    .bouton-scan:disabled { opacity: 0.6; }
    .erreur { color: var(--error-color, #b3261e); }
    .derniere-fiche {
      margin: 16px 0; padding: 8px; border-radius: 8px; background: var(--secondary-background-color);
      display: flex; flex-direction: column; align-items: center; gap: 4px;
    }
    .derniere-fiche img { max-height: 72px; max-width: 100%; border-radius: 6px; }
    .derniere-fiche-ignores, .derniere-fiche-quantite {
      color: var(--secondary-text-color); font-size: 0.85rem; text-align: center;
    }
    .en-attente {
      text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 8px 0 0;
    }
    .bouton-saisie {
      display: block; width: 100%; min-height: 48px; margin-top: 16px; border-radius: 8px;
      border: 1px solid var(--divider-color, #ccc); background: transparent; color: var(--primary-text-color);
    }
    .saisie-manuelle { display: flex; gap: 8px; margin-top: 8px; }
    .champ-code { flex: 1; min-height: 48px; font-size: 1rem; padding: 4px 8px; box-sizing: border-box; }
    .valider-saisie {
      min-height: 48px; min-width: 62px; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
  `,e([de({attribute:!1})],Pe.prototype,"fenetre",void 0),e([de({attribute:!1})],Pe.prototype,"derniereFiche",void 0),e([de({attribute:!1})],Pe.prototype,"session",void 0),e([de({attribute:!1})],Pe.prototype,"enAttente",void 0),e([he()],Pe.prototype,"saisieOuverte",void 0),e([he()],Pe.prototype,"codeSaisi",void 0),e([he()],Pe.prototype,"enCours",void 0),e([he()],Pe.prototype,"erreur",void 0),Pe=e([ce("home-stock-scanner")],Pe);let je=class extends ae{constructor(){super(...arguments),this.donnees=null,this.enAttente=0,this.ligneArmee=null,this.prixSaisiParLigne={},this.erreurPrixParLigne={},this.deltaParLigne={},this.quantiteVueParLigne={},this.seulementHorsListe=!1}willUpdate(e){if(e.has("donnees")){this.ligneArmee=null;for(const e of this.donnees?.lines??[])if(this.quantiteVueParLigne[e.id]!==e.quantity&&(this.quantiteVueParLigne[e.id]=e.quantity,this.deltaParLigne[e.id])){const{[e.id]:t,...i}=this.deltaParLigne;this.deltaParLigne=i}}}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()),i.sort.then(e=>"envoyee"===e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}quantiteAffichee(e){return e.quantity+(this.deltaParLigne[e.id]??0)}ajusterQuantite(e,t){this.ligneArmee=null;const i=(this.deltaParLigne[e.id]??0)+t,r=e.quantity+i;r<=0||(this.deltaParLigne={...this.deltaParLigne,[e.id]:i},this.ecrire("home_stock/session/update_line",{line_id:e.id,quantity:r}))}saisirPrix(e,t){this.ligneArmee=null,this.prixSaisiParLigne={...this.prixSaisiParLigne,[e.id]:t}}validerPrix(e){this.ligneArmee=null;const t=this.prixSaisiParLigne[e.id];if(void 0===t)return;const i=Ce(t,e.base_unit,e.net_quantity);if(null===i)return void(this.erreurPrixParLigne={...this.erreurPrixParLigne,[e.id]:"Prix non enregistré : poids du paquet inconnu."});if(this.erreurPrixParLigne[e.id]){const{[e.id]:t,...i}=this.erreurPrixParLigne;this.erreurPrixParLigne=i}this.ecrire("home_stock/session/update_line",{line_id:e.id,unit_price:i});const{[e.id]:r,...s}=this.prixSaisiParLigne;this.prixSaisiParLigne=s}supprimer(e){this.ecrire("home_stock/session/remove_line",{line_id:e.id}),this.ligneArmee=null}passerEnCaisse(){this.ligneArmee=null,this.ecrire("home_stock/session/checkout",{})}valeurPrix(e){const t=this.prixSaisiParLigne[e.id];return void 0!==t?t:Ae(e.unit_price,e.base_unit,e.net_quantity)}rendreLigne(e){const t=function(e){return"piece"===e.base_unit?1:e.net_quantity&&e.net_quantity>0?e.net_quantity:1}(e),i=this.quantiteAffichee(e),r=e.article_label??e.product_name;return B`
      <article class="ligne">
        ${e.image?B`<img class="image" src=${e.image} alt="" />`:H}
        <div class="infos">
          <p class="nom">${r}${e.brand?` — ${e.brand}`:""}</p>
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
          ${this.erreurPrixParLigne[e.id]?B`
            <p class="erreur-prix">${this.erreurPrixParLigne[e.id]}</p>
          `:H}
        </div>
        ${this.ligneArmee===e.id?B`
          <div class="confirmation-suppression">
            <button class="confirmer-suppression" @click=${()=>this.supprimer(e)}>Confirmer</button>
            <button class="annuler-suppression" @click=${()=>{this.ligneArmee=null}}>Annuler</button>
          </div>
        `:B`
          <button class="supprimer" aria-label="Retirer du panier" @click=${()=>{this.ligneArmee=e.id}}>
            ×
          </button>
        `}
      </article>
    `}rendreRepartition(e){if(void 0===e.estimated)return H;const t=e.unpriced_lines??0,i=(e.list_items??0)>0?`${e.checked_items??0} / ${e.list_items} de la liste`:null;return B`
      <p class="repartition">${`dont ${ze(e.estimated)} estimé`+(t>0?`, ${t} ligne${t>1?"s":""} sans prix`:"")}</p>
      ${i?B`<p class="progression">${i}</p>`:H}
    `}render(){const e=this.donnees;if(!e)return B`<p class="vide">Aucune session de courses ouverte.</p>`;const t=function(e){const t=[];for(const i of e){const e=i.aisle_name??"Sans rayon",r=t[t.length-1];r&&r.rayon===e?r.lignes.push(i):t.push({rayon:e,lignes:[i]})}return t}(e.lines),i="shopping"!==e.session.state;return B`
      <section class="entete">
        <p class="magasin">${e.session.store??"Sans enseigne"}</p>
        <p class="total">${ze(e.totals.total)}</p>
      </section>

      ${this.rendreRepartition(e.totals)}

      ${this.enAttente>0?B`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:H}

      ${0===e.lines.length?B`<p class="vide">Le panier est vide.</p>`:H}

      ${(e.totals.off_list_lines??0)>0?B`
        <button class="hors-liste"
          aria-pressed=${this.seulementHorsListe?"true":"false"}
          @click=${()=>{this.seulementHorsListe=!this.seulementHorsListe}}>
          ${`${e.totals.off_list_lines} hors liste`}
        </button>
      `:H}

      ${t.map(e=>B`
        <section class="rayon">
          <h3 class="rayon-nom">${e.rayon}</h3>
          ${e.lignes.map(e=>this.rendreLigne(e))}
        </section>
      `)}

      <button class="checkout" ?disabled=${0===e.totals.lines||i} @click=${this.passerEnCaisse}>
        ${i?"Déjà en caisse":"Passage en caisse"}
      </button>
    `}};je.styles=o`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .entete { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
    .magasin { font-weight: 600; margin: 0; }
    .total { font-size: 1.3rem; font-weight: 700; margin: 0; }
    .repartition, .progression { margin: 0 0 4px; font-size: 0.85rem; color: var(--secondary-text-color); }
    .hors-liste {
      min-height: 48px; width: 100%; border-radius: 8px; border: none; font-size: 0.9rem;
      background: var(--secondary-background-color); color: var(--primary-text-color);
      margin-bottom: 8px;
    }
    .hors-liste[aria-pressed='true'] { background: var(--primary-color); color: var(--text-primary-color, #fff); }
    .en-attente { text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 4px 0 8px; }
    .vide { color: var(--secondary-text-color); text-align: center; }
    .rayon-nom {
      margin: 16px 0 4px; font-size: 0.9rem; text-transform: uppercase;
      color: var(--secondary-text-color); letter-spacing: 0.04em;
    }
    .ligne {
      display: flex; align-items: center; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .image { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; flex-shrink: 0; }
    .infos { flex: 1; min-width: 0; }
    .nom { margin: 0 0 4px; }
    .quantite { display: flex; align-items: center; gap: 8px; }
    .quantite button {
      min-width: 48px; min-height: 48px; font-size: 1.3rem; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .quantite button:disabled { opacity: 0.5; }
    .valeur-quantite { min-width: 56px; text-align: center; }
    .prix-label { display: block; font-size: 0.85rem; margin-top: 4px; }
    .prix-champ { min-height: 48px; width: 100%; box-sizing: border-box; font-size: 1rem; padding: 4px 8px; }
    .erreur-prix { color: var(--error-color, #b3261e); font-size: 0.8rem; margin: 4px 0 0; }
    .supprimer {
      min-width: 48px; min-height: 48px; border-radius: 8px; border: none; font-size: 1.2rem;
      background: var(--error-color, #b3261e); color: #fff; flex-shrink: 0;
    }
    .confirmation-suppression { display: flex; flex-direction: column; gap: 4px; flex-shrink: 0; }
    .confirmer-suppression, .annuler-suppression {
      min-height: 48px; min-width: 88px; border-radius: 8px; border: none; font-size: 0.9rem;
    }
    .confirmer-suppression { background: var(--error-color, #b3261e); color: #fff; }
    .annuler-suppression { background: var(--secondary-background-color); color: var(--primary-text-color); }
    .checkout {
      display: block; width: 100%; min-height: 62px; font-size: 1.2rem; border-radius: 12px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff); margin-top: 16px;
    }
    .checkout:disabled { opacity: 0.5; }
  `,e([de({attribute:!1})],je.prototype,"donnees",void 0),e([de({attribute:!1})],je.prototype,"connexion",void 0),e([de({attribute:!1})],je.prototype,"file",void 0),e([de({attribute:!1})],je.prototype,"enAttente",void 0),e([he()],je.prototype,"ligneArmee",void 0),e([he()],je.prototype,"prixSaisiParLigne",void 0),e([he()],je.prototype,"erreurPrixParLigne",void 0),e([he()],je.prototype,"deltaParLigne",void 0),e([he()],je.prototype,"seulementHorsListe",void 0),je=e([ce("home-stock-panier")],je);let Le=class extends ae{constructor(){super(...arguments),this.donnees=null,this.enAttente=0,this.magasins=[],this.magasinChoisi=null,this.magasinSaisi="",this.erreurMagasins=null,this.clotureArmee=!1,this.enCours=!1,this.message=null}connectedCallback(){super.connectedCallback(),this.chargerMagasins()}willUpdate(e){e.has("donnees")&&(this.clotureArmee=!1)}async chargerMagasins(){if(this.erreurMagasins=null,this.donnees?.stores?.length&&(this.magasins=this.donnees.stores),this.connexion)try{const e=await this.connexion.appeler("home_stock/stores/list");this.magasins=e.stores}catch{this.erreurMagasins="Impossible de récupérer les magasins connus. Saisissez-en un."}}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()),i.sort.then(e=>"envoyee"===e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}get chargeMagasin(){const e=this.magasinSaisi.trim();return e?{store:e}:this.magasinChoisi?{store_id:this.magasinChoisi.id}:{}}get magasinRetenu(){const e=this.magasinSaisi.trim();return e||(this.magasinChoisi?.name??null)}async ouvrir(){if(this.enCours)return;this.enCours=!0,this.message=null;const e=await this.ecrire("home_stock/session/start",this.chargeMagasin);this.enCours=!1,e?this.dispatchEvent(new CustomEvent("session-changee",{detail:{action:"ouverte"},bubbles:!0,composed:!0})):this.message="Envoi en attente de réseau : la session s’ouvrira à la reconnexion."}async clore(){if(!this.clotureArmee||this.enCours)return;this.enCours=!0,this.message=null;const e=await this.ecrire("home_stock/session/close",{});this.enCours=!1,this.clotureArmee=!1,e?this.dispatchEvent(new CustomEvent("session-changee",{detail:{action:"fermee"},bubbles:!0,composed:!0})):this.message="Envoi en attente de réseau : la session se clora à la reconnexion."}rendreOuverture(){return B`
      <h2 class="titre">Nouvelle session de courses</h2>
      <p class="explication">
        Choisissez le magasin : les scans partiront au panier au lieu d’aller directement au rangement.
      </p>

      ${this.magasins.length?B`
        <div class="pastilles">
          ${this.magasins.map(e=>B`
            <button class="pastille ${this.magasinChoisi?.id===e.id?"choisie":""}"
              aria-pressed=${this.magasinChoisi?.id===e.id?"true":"false"}
              @click=${()=>{this.magasinChoisi=e,this.magasinSaisi=""}}>
              ${e.name}
            </button>
          `)}
        </div>`:H}

      ${this.erreurMagasins?B`<p class="erreur">${this.erreurMagasins}</p>`:H}

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
    `}rendreCloture(e){const t="shopping"===e.session.state,i=e.totals.pending;return B`
      <h2 class="titre">${t?"Session en cours":"Courses à ranger"}</h2>
      <p class="magasin-retenu">${e.session.store??"Sans enseigne"}</p>
      <p class="resume">
        ${e.totals.lines} ligne${e.totals.lines>1?"s":""} —
        ${r=e.totals.total,`${r.toFixed(2).replace(".",",")} €`}
      </p>
      ${t&&(e.totals.list_items??0)>0?B`
        <button class="emporter-liste" @click=${()=>this.dispatchEvent(new CustomEvent("aller-liste",{bubbles:!0,composed:!0}))}>
          ${`Emporter la liste (${e.totals.list_items})`}
        </button>
      `:H}

      ${t?H:B`
        <button class="photographier" @click=${()=>this.dispatchEvent(new CustomEvent("ticket-ouvert",{detail:{ticket:null,agent_configure:!0},bubbles:!0,composed:!0}))}>
          Photographier le ticket
        </button>
      `}

      ${i>0?B`
        <p class="restantes">
          ${i} ligne${i>1?"s":""} pas encore rangée${i>1?"s":""}.
          Clore la session les abandonne : rien n’entrera en stock pour elles.
        </p>`:H}

      ${this.clotureArmee?B`
        <div class="confirmation-cloture">
          <button class="confirmer-cloture" ?disabled=${this.enCours} @click=${this.clore}>
            Confirmer la clôture
          </button>
          <button class="annuler-cloture" @click=${()=>{this.clotureArmee=!1}}>
            Annuler
          </button>
        </div>
      `:B`
        <button class="clore-session" @click=${()=>{this.clotureArmee=!0}}>
          Clore la session
        </button>
      `}
    `;var r}render(){return B`
      ${this.enAttente>0?B`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:H}
      ${this.donnees?this.rendreCloture(this.donnees):this.rendreOuverture()}
      ${this.message?B`<p class="message">${this.message}</p>`:H}
    `}};function Re(e,t){const i=new Date(t.getFullYear(),t.getMonth(),t.getDate()+e);return`${String(i.getFullYear()).padStart(4,"0")}-${String(i.getMonth()+1).padStart(2,"0")}-${String(i.getDate()).padStart(2,"0")}`}Le.styles=o`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .titre { margin: 0 0 8px; font-size: 1.2rem; }
    .explication, .resume, .magasin-retenu { margin: 4px 0; color: var(--secondary-text-color); }
    .en-attente { text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 0 0 8px; }
    .pastilles { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
    .pastille {
      min-height: 48px; min-width: 88px; padding: 0 16px; border-radius: 24px; border: none;
      font-size: 1rem; background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .pastille.choisie { background: var(--primary-color); color: var(--text-primary-color, #fff); }
    .emporter-liste, .photographier {
      display: block; width: 100%; min-height: 62px; font-size: 1.05rem; border-radius: 12px;
      border: none; margin: 8px 0; background: var(--secondary-background-color);
      color: var(--primary-text-color);
    }
    .magasin-label { display: block; margin: 8px 0; }
    .champ-magasin {
      min-height: 48px; width: 100%; box-sizing: border-box; font-size: 1rem; padding: 4px 8px;
    }
    .erreur { color: var(--error-color, #b3261e); font-size: 0.9rem; }
    .restantes { color: var(--error-color, #b3261e); font-size: 0.9rem; }
    .message { color: var(--secondary-text-color); font-size: 0.9rem; }
    .ouvrir-session {
      display: block; width: 100%; min-height: 62px; font-size: 1.2rem; border-radius: 12px;
      border: none; background: var(--primary-color); color: var(--text-primary-color, #fff);
      margin-top: 16px;
    }
    .ouvrir-session:disabled { opacity: 0.5; }
    .clore-session, .confirmer-cloture, .annuler-cloture {
      display: block; width: 100%; min-height: 62px; font-size: 1.1rem; border-radius: 12px;
      border: none; margin-top: 12px;
    }
    .clore-session, .confirmer-cloture {
      background: var(--error-color, #b3261e); color: #fff;
    }
    .annuler-cloture {
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .confirmation-cloture { display: block; }
  `,e([de({attribute:!1})],Le.prototype,"donnees",void 0),e([de({attribute:!1})],Le.prototype,"connexion",void 0),e([de({attribute:!1})],Le.prototype,"file",void 0),e([de({attribute:!1})],Le.prototype,"enAttente",void 0),e([he()],Le.prototype,"magasins",void 0),e([he()],Le.prototype,"magasinChoisi",void 0),e([he()],Le.prototype,"magasinSaisi",void 0),e([he()],Le.prototype,"erreurMagasins",void 0),e([he()],Le.prototype,"clotureArmee",void 0),e([he()],Le.prototype,"enCours",void 0),e([he()],Le.prototype,"message",void 0),Le=e([ce("home-stock-session")],Le);let Me=class extends ae{constructor(){super(...arguments),this.lignes=[],this.enAttente=0,this.emplacements=[],this.erreurEmplacements=null,this.emplacementChoisi={},this.enCours=new Set,this.aEuDesLignes=!1,this.termineEnvoye=!1}connectedCallback(){super.connectedCallback(),this.chargerEmplacements()}willUpdate(e){e.has("lignes")&&this.lignes.length>0&&(this.aEuDesLignes=!0)}updated(){this.aEuDesLignes&&0===this.lignes.length&&!this.termineEnvoye&&(this.termineEnvoye=!0,this.dispatchEvent(new CustomEvent("termine",{bubbles:!0,composed:!0})))}async chargerEmplacements(){if(this.connexion){this.erreurEmplacements=null;try{const e=await this.connexion.appeler("home_stock/locations/list");this.emplacements=e.locations}catch{this.erreurEmplacements="Impossible de récupérer les emplacements. Vérifiez la connexion."}}}emplacementPour(e){const t=this.emplacementChoisi[String(e.id)];return void 0!==t?t:e.default_location_id}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()),i.sort.then(e=>"envoyee"===e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}ranger(e,t){const i=this.emplacementPour(e);if(null===i)return;const r=String(e.id);if(this.enCours.has(r))return;this.enCours=new Set(this.enCours).add(r);const s=()=>{const e=new Set(this.enCours);e.delete(r),this.enCours=e};"session"===e.source?this.ecrire("home_stock/session/store_line",{line_id:e.id,location_id:i,best_before:t.date}).then(s):this.ecrire("home_stock/stock/add",{article_id:e.article_id,quantity:e.quantity,location_id:i,best_before:t.date,price_per_base_unit:e.unit_price,idempotency_key:`rangement:${e.id}`}).then(t=>{s(),t&&this.dispatchEvent(new CustomEvent("ligne-autonome-rangee",{detail:{id:e.id},bubbles:!0,composed:!0}))})}rendreLigne(e){const t=String(e.id),i=this.enCours.has(t),r=this.emplacementPour(e),s=function(e,t){const i=[];t&&t>0&&i.push({libelle:`+${t} j (habituel)`,date:Re(t,e)}),i.push({libelle:"+3 j",date:Re(3,e)},{libelle:"+1 sem",date:Re(7,e)},{libelle:"+1 mois",date:Re(31,e)});const r=new Set,s=i.filter(e=>e.date&&!r.has(e.date)&&r.add(e.date));return[...s,{libelle:"Sans DLC",date:null}]}(new Date,e.default_shelf_life_days);return B`
      <article class="ligne">
        ${e.image?B`<img class="image" src=${e.image} alt="" />`:H}
        <div class="infos">
          <p class="nom">${function(e){return"session"===e.source?e.article_label??e.product_name:e.product_name}(e)}${e.brand?` — ${e.brand}`:""}</p>
          <p class="quantite">
            ${e.quantity}${"piece"!==e.base_unit?` ${e.base_unit}`:""}
          </p>
          <label class="emplacement-label">
            Emplacement
            <select class="emplacement-champ" .value=${null!==r?String(r):""}
              ?disabled=${i}
              @change=${e=>{this.emplacementChoisi={...this.emplacementChoisi,[t]:Number(e.target.value)}}}>
              ${null===r?B`
                <option value="" disabled selected>Choisir…</option>
              `:H}
              ${this.emplacements.map(e=>B`
                <option value=${String(e.id)} ?selected=${e.id===r}>${e.name}</option>
              `)}
            </select>
          </label>
          ${null===r?B`
            <p class="emplacement-manquant">Choisissez un emplacement avant de ranger.</p>
          `:H}
          ${this.erreurEmplacements?B`<p class="erreur">${this.erreurEmplacements}</p>`:H}
          <div class="raccourcis-dlc">
            ${s.map(t=>B`
              <button class="raccourci-dlc" ?disabled=${i||null===r}
                @click=${()=>this.ranger(e,t)}>
                ${i?"Rangement…":t.libelle}
              </button>
            `)}
          </div>
        </div>
      </article>
    `}render(){if(0===this.lignes.length)return B`<p class="tout-range">Tout est rangé.</p>`;const e=function(e,t,i=e=>e.default_location_id){const r=e=>null===e?"Emplacement à choisir":t.find(t=>t.id===e)?.name??"Emplacement à choisir",s=[];for(const t of e){const e=i(t);let n=s.find(t=>t.emplacementId===e);n||(n={emplacementId:e,nom:r(e),lignes:[]},s.push(n)),n.lignes.push(t)}return s}(this.lignes,this.emplacements,e=>this.emplacementPour(e));return B`
      ${this.enAttente>0?B`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:H}
      ${e.map(e=>B`
        <section class="emplacement">
          <h3 class="emplacement-nom">${e.nom}</h3>
          ${e.lignes.map(e=>this.rendreLigne(e))}
        </section>
      `)}
    `}};function Fe(e){const t=e.trim();if(""===t)return{ok:!0,valeur:null};const i=Number(t.replace(",","."));return Number.isFinite(i)?{ok:!0,valeur:i}:{ok:!1}}function Oe(e){return(Math.round(100*e)/100).toString().replace(".",",")}Me.styles=o`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .tout-range { text-align: center; font-size: 1.2rem; margin-top: 32px; }
    .en-attente { text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 0 0 8px; }
    .emplacement-nom {
      margin: 16px 0 4px; font-size: 0.9rem; text-transform: uppercase;
      color: var(--secondary-text-color); letter-spacing: 0.04em;
    }
    .ligne {
      display: flex; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .image { width: 48px; height: 48px; object-fit: cover; border-radius: 6px; flex-shrink: 0; }
    .infos { flex: 1; min-width: 0; }
    .nom { margin: 0 0 4px; }
    .quantite { margin: 0 0 4px; color: var(--secondary-text-color); }
    .emplacement-label { display: block; font-size: 0.85rem; margin-bottom: 8px; }
    .emplacement-champ { min-height: 48px; width: 100%; box-sizing: border-box; font-size: 1rem; }
    .emplacement-manquant { color: var(--error-color, #b3261e); font-size: 0.85rem; margin: 0 0 8px; }
    .erreur { color: var(--error-color, #b3261e); font-size: 0.85rem; }
    .raccourcis-dlc { display: flex; flex-wrap: wrap; gap: 8px; }
    .raccourci-dlc {
      min-height: 48px; padding: 0 12px; border-radius: 8px; border: none; font-size: 0.95rem;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .raccourci-dlc:disabled { opacity: 0.5; }
  `,e([de({attribute:!1})],Me.prototype,"lignes",void 0),e([de({attribute:!1})],Me.prototype,"connexion",void 0),e([de({attribute:!1})],Me.prototype,"file",void 0),e([de({attribute:!1})],Me.prototype,"enAttente",void 0),e([he()],Me.prototype,"emplacements",void 0),e([he()],Me.prototype,"erreurEmplacements",void 0),e([he()],Me.prototype,"emplacementChoisi",void 0),e([he()],Me.prototype,"enCours",void 0),Me=e([ce("home-stock-rangement")],Me);const Ne=[[1/4,"¼"],[1/3,"⅓"],[.5,"½"],[2/3,"⅔"],[3/4,"¾"]];const Te={g:"g",ml:"ml",piece:""};function Ie(e,t,i,r){if(null===e)return"";const s=r??i;return s?`${Oe(e)} ${function(e,t){if(t<2)return e;const[i,...r]=e.split(" ");return[i.endsWith("s")?i:`${i}s`,...r].join(" ")}(s,e)}`:"piece"===t?function(e){const t=Math.floor(e),i=e-t;if(i<.005)return String(t);for(const[e,r]of Ne)if(Math.abs(i-e)<.005)return 0===t?r:`${t} ${r}`;return Oe(e)}(e):`${Oe(e)} ${Te[t]}`.trim()}function De(e){return{name:e.name,aisle_id:null!==e.aisle_id?String(e.aisle_id):"",default_location_id:null!==e.default_location_id?String(e.default_location_id):"",min_quantity:null!==e.min_quantity?String(e.min_quantity):"",default_shelf_life_days:null!==e.default_shelf_life_days?String(e.default_shelf_life_days):""}}function Ue(e){const t=e.trim();return""===t?null:Number(t)}const Be={min_quantity:"Seuil de réapprovisionnement",default_shelf_life_days:"Durée de conservation"};function Ve(e,t,i,r){const s=Fe(t[e]);return s.ok?(s.valeur!==i[e]&&(r[e]=s.valeur),null):`${Be[e]} : nombre invalide (« ${t[e]} »).`}let He=class extends ae{constructor(){super(...arguments),this.enAttente=0,this.produits=[],this.rayons=[],this.emplacements=[],this.quantitesParProduit={},this.erreurChargement=null,this.recherche="",this.produitEditeId=null,this.produitEnEdition=null,this.brouillon=null,this.erreurEdition=null,this.enCours=!1,this.enAttenteEnvoi=!1,this.nomRayon=e=>null===e?"Sans rayon":this.rayons.find(t=>t.id===e)?.name??"Sans rayon"}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(this.connexion){this.erreurChargement=null;try{const[e,t,i,r]=await Promise.all([this.connexion.appeler("home_stock/products/list"),this.connexion.appeler("home_stock/aisles/list"),this.connexion.appeler("home_stock/locations/list"),this.connexion.appeler("home_stock/batches/list")]);this.produits=e.products,this.rayons=t.aisles,this.emplacements=i.locations;const s={};for(const e of r.batches)s[e.product_id]=(s[e.product_id]??0)+e.remaining;this.quantitesParProduit=s}catch{this.erreurChargement="Impossible de récupérer le catalogue. Vérifiez la connexion."}}}nomEmplacement(e){return null===e?"Aucun":this.emplacements.find(t=>t.id===e)?.name??"Aucun"}get produitsFiltres(){return function(e,t,i){const r=t.trim().toLowerCase();return r?e.filter(e=>e.name.toLowerCase().includes(r)||i(e.aisle_id).toLowerCase().includes(r)):e}(this.produits,this.recherche,this.nomRayon)}async ouvrirEdition(e){if(this.produitEditeId=e.id,this.produitEnEdition=e,this.brouillon=De(e),this.erreurEdition=null,this.enAttenteEnvoi=!1,this.connexion)try{const t=await this.connexion.appeler("home_stock/product/get",{product_id:e.id});this.produitEditeId===e.id&&(this.produitEnEdition=t.product,this.brouillon=De(t.product))}catch{}}fermerEdition(){this.produitEditeId=null,this.produitEnEdition=null,this.brouillon=null,this.erreurEdition=null,this.enAttenteEnvoi=!1}modifierBrouillon(e,t){this.brouillon&&(this.brouillon={...this.brouillon,[e]:t})}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()),i.sort.then(e=>"envoyee"===e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}mangerProduit(e){this.dispatchEvent(new CustomEvent("manger-produit",{detail:{product_id:e.id},bubbles:!0,composed:!0}))}async enregistrer(){const e=this.produitEnEdition,t=this.brouillon;if(!e||!t||this.enCours)return;const i=function(e,t){const i={},r=e.name.trim();r&&r!==t.name&&(i.name=r),Ue(e.aisle_id)!==t.aisle_id&&(i.aisle_id=Ue(e.aisle_id)),Ue(e.default_location_id)!==t.default_location_id&&(i.default_location_id=Ue(e.default_location_id));const s=Ve("min_quantity",e,t,i);if(s)return{ok:!1,erreur:s};const n=Ve("default_shelf_life_days",e,t,i);return n?{ok:!1,erreur:n}:{ok:!0,champs:i}}(t,e);if(!i.ok)return void(this.erreurEdition=i.erreur);if(0===Object.keys(i.champs).length)return void this.fermerEdition();this.enCours=!0,this.erreurEdition=null,this.enAttenteEnvoi=!1;const r=await this.ecrire("home_stock/product/update",{product_id:e.id,fields:i.champs});this.enCours=!1,r?(await this.charger(),this.fermerEdition()):this.enAttenteEnvoi=!0}rendreEdition(e){const t=this.brouillon;return t?B`
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
            ${this.rayons.map(e=>B`<option value=${String(e.id)}>${e.name}</option>`)}
          </select>
        </label>
        <label class="champ">
          Emplacement par défaut
          <select class="champ-emplacement" .value=${t.default_location_id}
            @change=${e=>this.modifierBrouillon("default_location_id",e.target.value)}>
            <option value="">Aucun</option>
            ${this.emplacements.map(e=>B`<option value=${String(e.id)}>${e.name}</option>`)}
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
        <p class="champ-lecture-seule">
          Catégorie : ${e.category_id??"aucune"} (identifiant interne) — non modifiable ici : aucune
          liste de noms n'existe côté serveur pour vérifier une saisie.
        </p>
        <p class="champ-lecture-seule">
          Unité de base : ${"piece"===e.base_unit?"à la pièce":e.base_unit}
          — se change uniquement par une conversion, pas depuis cet écran.
        </p>
        ${this.enAttenteEnvoi?B`
          <p class="etat-envoi">Enregistrement en file d'attente (hors ligne) ou refusé — voir le message ci-dessus.</p>
        `:H}
        ${this.erreurEdition?B`<p class="erreur">${this.erreurEdition}</p>`:H}
        <div class="actions-edition">
          <button class="enregistrer" ?disabled=${this.enCours} @click=${this.enregistrer}>
            ${this.enCours?"Enregistrement…":"Enregistrer"}
          </button>
          <button class="annuler" ?disabled=${this.enCours} @click=${()=>this.fermerEdition()}>Annuler</button>
        </div>
      </div>
    `:H}rendreLigne(e){const t=this.quantitesParProduit[e.id]??0,i="piece"!==e.base_unit?` ${e.base_unit}`:"";return B`
      <article class="ligne">
        <div class="infos">
          <p class="nom">${e.name}</p>
          <p class="meta">
            ${this.nomRayon(e.aisle_id)} · en stock : ${t}${i}
            ${null!==e.min_quantity?B` · seuil : ${e.min_quantity}${i}`:H}
            · emplacement : ${this.nomEmplacement(e.default_location_id)}
          </p>
        </div>
        <button class="manger" @click=${()=>this.mangerProduit(e)}>Manger</button>
        <button class="modifier" @click=${()=>this.ouvrirEdition(e)}>Modifier</button>
        ${this.produitEditeId===e.id?this.rendreEdition(this.produitEnEdition??e):H}
      </article>
    `}render(){return B`
      <input class="recherche" type="search" placeholder="Rechercher un produit ou un rayon…"
        .value=${this.recherche}
        @input=${e=>{this.recherche=e.target.value}} />

      ${this.enAttente>0?B`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:H}

      ${this.erreurChargement?B`
        <p class="erreur">${this.erreurChargement}</p>
        <button class="reessayer" @click=${()=>{this.charger()}}>Réessayer</button>
      `:H}

      ${this.erreurChargement||0!==this.produitsFiltres.length?H:B`
        <p class="vide">Aucun produit.</p>
      `}

      <div class="liste">
        ${this.produitsFiltres.map(e=>this.rendreLigne(e))}
      </div>
    `}};He.styles=o`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .recherche {
      display: block; width: 100%; min-height: 48px; box-sizing: border-box; font-size: 1rem;
      padding: 4px 12px; border-radius: 8px; border: 1px solid var(--divider-color, #ddd); margin-bottom: 8px;
    }
    .en-attente { text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 0 0 8px; }
    .vide { color: var(--secondary-text-color); text-align: center; }
    .erreur { color: var(--error-color, #b3261e); font-size: 0.9rem; }
    .reessayer {
      min-height: 48px; width: 100%; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .ligne {
      display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .infos { flex: 1; min-width: 0; }
    .nom { margin: 0 0 4px; font-weight: 600; }
    .meta { margin: 0; color: var(--secondary-text-color); font-size: 0.85rem; }
    .modifier {
      min-height: 48px; min-width: 48px; padding: 0 16px; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff); flex-shrink: 0;
    }
    .manger {
      min-height: 48px; min-width: 48px; padding: 0 16px; border-radius: 8px; border: none;
      background: var(--secondary-background-color); color: var(--primary-text-color); flex-shrink: 0;
    }
    .edition {
      flex: 1 0 100%; display: flex; flex-direction: column; gap: 8px; margin-top: 8px;
      padding: 12px; border-radius: 8px; background: var(--secondary-background-color);
      box-sizing: border-box;
    }
    .champ { display: block; font-size: 0.85rem; }
    .champ-nom, .champ-rayon, .champ-emplacement, .champ-seuil, .champ-conservation {
      display: block; width: 100%; min-height: 48px; box-sizing: border-box; font-size: 1rem;
      padding: 4px 8px; margin-top: 4px;
    }
    .champ-lecture-seule { color: var(--secondary-text-color); font-size: 0.85rem; margin: 4px 0; }
    .etat-envoi { color: var(--secondary-text-color); font-size: 0.85rem; }
    .actions-edition { display: flex; flex-wrap: wrap; gap: 8px; }
    .enregistrer, .annuler {
      min-height: 48px; flex: 1; border-radius: 8px; border: none; font-size: 0.95rem;
    }
    .enregistrer { background: var(--primary-color); color: var(--text-primary-color, #fff); }
    .enregistrer:disabled { opacity: 0.5; }
    .annuler { background: var(--secondary-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color, #ddd); }
  `,e([de({attribute:!1})],He.prototype,"connexion",void 0),e([de({attribute:!1})],He.prototype,"file",void 0),e([de({attribute:!1})],He.prototype,"enAttente",void 0),e([he()],He.prototype,"produits",void 0),e([he()],He.prototype,"rayons",void 0),e([he()],He.prototype,"emplacements",void 0),e([he()],He.prototype,"quantitesParProduit",void 0),e([he()],He.prototype,"erreurChargement",void 0),e([he()],He.prototype,"recherche",void 0),e([he()],He.prototype,"produitEditeId",void 0),e([he()],He.prototype,"produitEnEdition",void 0),e([he()],He.prototype,"brouillon",void 0),e([he()],He.prototype,"erreurEdition",void 0),e([he()],He.prototype,"enCours",void 0),e([he()],He.prototype,"enAttenteEnvoi",void 0),He=e([ce("home-stock-catalogue")],He);const Je=new Set(["Une resynchronisation Open Food Facts est déjà en cours."]);function Qe(e,t,i){const r=t+i;if(r<0||r>=e.length)return null;const s=[...e];return[s[t],s[r]]=[s[r],s[t]],s}let We=class extends ae{constructor(){super(...arguments),this.enAttente=0,this.rayons=[],this.emplacements=[],this.erreurChargement=null,this.magasins=[],this.magasinOuvert=null,this.parcours=null,this.fusionArmee=null,this.erreurFusion=null,this.recurrentes=[],this.saisieRecurrente="",this.saisieJours="",this.agentTicket=null,this.tailleTickets=null,this.resyncEnCours=!1,this.messageResync=null,this.erreurResync=null}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(this.connexion){this.erreurChargement=null;try{const[e,t,i,r]=await Promise.all([this.connexion.appeler("home_stock/aisles/list"),this.connexion.appeler("home_stock/locations/list"),this.connexion.appeler("home_stock/stores/list"),this.connexion.appeler("home_stock/recurring/list")]);this.rayons=e?.aisles??[],this.emplacements=t?.locations??[],this.magasins=i?.stores??[],this.recurrentes=r?.recurring??[]}catch{this.erreurChargement="Impossible de récupérer les rayons et les emplacements. Vérifiez la connexion."}}}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}async deplacerRayon(e,t){const i=Qe(this.rayons,e,t);if(null===i)return;if(this.rayons=i,!this.file)return;const r=this.file.ajouter("home_stock/aisles/reorder",{aisle_ids:i.map(e=>e.id)});this.avertirFile(),await this.file.rejouer(),this.avertirFile(),"refusee"===await r.sort&&await this.charger()}async resynchroniser(){if(this.connexion&&!this.resyncEnCours){this.resyncEnCours=!0,this.messageResync=null,this.erreurResync=null;try{await this.connexion.appelerService("home_stock","resync_off",{all:!0}),this.messageResync="Resynchronisation lancée en tâche de fond — environ 40 minutes pour tout le catalogue. Les champs corrigés à la main ne sont jamais écrasés."}catch(e){this.erreurResync=function(e){const t=e&&"object"==typeof e&&"message"in e&&"string"==typeof e.message?e.message:null;return null!==t&&Je.has(t)?t:"La resynchronisation n'a pas pu être lancée."}(e)}finally{this.resyncEnCours=!1}}}rendreRayons(){return 0===this.rayons.length?B`<p class="vide">Aucun rayon.</p>`:B`
      <ul class="liste-rayons">
        ${this.rayons.map((e,t)=>B`
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
    `}async ouvrirMagasin(e){if(this.fusionArmee=null,this.erreurFusion=null,this.magasinOuvert===e.id)return this.magasinOuvert=null,void(this.parcours=null);this.magasinOuvert=e.id,this.parcours=null,this.connexion&&(this.parcours=await this.connexion.appeler("home_stock/store/aisles",{store_id:e.id}))}async deplacerRayonMagasin(e,t){const i=this.parcours;if(!i||!this.connexion)return;const r=Qe(i.aisles,e,t);null!==r&&(this.parcours=await this.connexion.appeler("home_stock/store/reorder_aisles",{store_id:i.store_id,aisle_ids:r.map(e=>e.aisle_id)}))}async reprendreApprentissage(e){const t=this.parcours;t&&this.connexion&&(this.parcours=await this.connexion.appeler("home_stock/store/unpin_aisle",{store_id:t.store_id,aisle_id:e}))}async fusionner(e){const t=this.magasins.find(t=>t.id!==e);if(t&&this.connexion){this.erreurFusion=null;try{const i=await this.connexion.appeler("home_stock/store/merge",{keep_id:t.id,merge_id:e});this.magasins=i.stores}catch(e){this.erreurFusion=e?.message??"Fusion impossible."}this.fusionArmee=null}}async enregistrerRecurrente(){const e=this.saisieRecurrente.trim(),t=Number.parseInt(this.saisieJours,10);if(!e||!Number.isFinite(t)||!this.connexion)return;const i=await this.connexion.appeler("home_stock/recurring/save",{free_text:e,every_days:t});this.recurrentes=i.recurring,this.saisieRecurrente="",this.saisieJours=""}async supprimerRecurrente(e){if(!this.connexion)return;const t=await this.connexion.appeler("home_stock/recurring/delete",{recurring_id:e});this.recurrentes=t.recurring}rendreMagasins(){return 0===this.magasins.length?B`<p class="vide">Aucun magasin connu.</p>`:B`
      <ul class="liste-magasins">
        ${this.magasins.map(e=>B`
          <li class="magasin">
            <button class="magasin-onglet"
              aria-pressed=${this.magasinOuvert===e.id?"true":"false"}
              @click=${()=>{this.ouvrirMagasin(e)}}>
              ${e.name}
            </button>
            ${this.magasins.length>1?B`
              ${this.fusionArmee===e.id?B`
                <button class="confirmer-fusion"
                  @click=${()=>{this.fusionner(e.id)}}>Confirmer</button>
                <button class="annuler-fusion"
                  @click=${()=>{this.fusionArmee=null}}>Annuler</button>
              `:B`
                <button class="fusionner"
                  @click=${()=>{this.fusionArmee=e.id}}>Fusionner</button>
              `}
            `:H}
            ${this.magasinOuvert===e.id?this.rendreParcours():H}
          </li>
        `)}
      </ul>
      ${this.erreurFusion?B`<p class="erreur-fusion">${this.erreurFusion}</p>`:H}
    `}rendreParcours(){const e=this.parcours;return e?B`
      <p class="fiabilite">${e.reliable?`Ordre appris de ce magasin (${e.observed_sessions} sessions).`:`${e.observed_sessions} session${e.observed_sessions>1?"s":""} sur ${e.required_sessions} : l’ordre par défaut est encore utilisé.`}</p>
      <ul class="liste-rayons-magasin">
        ${e.aisles.map((t,i)=>B`
          <li class="rayon-magasin ${"manual"===t.source?"epingle":""}">
            <span class="rayon-magasin-nom">${t.aisle_name}</span>
            ${"manual"===t.source?B`
              <span class="marque-epingle">épinglé</span>
              <button class="reprendre-apprentissage"
                @click=${()=>{this.reprendreApprentissage(t.aisle_id)}}>
                Reprendre l’apprentissage
              </button>
            `:H}
            <button class="monter-rayon-magasin" aria-label="Monter ${t.aisle_name}"
              ?disabled=${0===i}
              @click=${()=>{this.deplacerRayonMagasin(i,-1)}}>▲</button>
            <button class="descendre-rayon-magasin" aria-label="Descendre ${t.aisle_name}"
              ?disabled=${i===e.aisles.length-1}
              @click=${()=>{this.deplacerRayonMagasin(i,1)}}>▼</button>
          </li>
        `)}
      </ul>
    `:B`<p class="vide">Chargement du parcours…</p>`}rendreRecurrentes(){return B`
      <ul class="liste-recurrentes">
        ${this.recurrentes.map(e=>B`
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
    `}rendreEmplacements(){return 0===this.emplacements.length?B`<p class="vide">Aucun emplacement.</p>`:B`
      <ul class="liste-emplacements">
        ${this.emplacements.map(e=>B`
          <li class="emplacement">
            <span class="emplacement-nom">${e.name}</span>
            <span class="emplacement-type">${e.kind}</span>
          </li>
        `)}
      </ul>
    `}render(){return B`
      ${this.enAttente>0?B`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:H}

      ${this.erreurChargement?B`
        <p class="erreur">${this.erreurChargement}</p>
        <button class="reessayer" @click=${()=>{this.charger()}}>Réessayer</button>
      `:H}

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
        ${this.messageResync?B`<p class="message-resync">${this.messageResync}</p>`:H}
        ${this.erreurResync?B`<p class="erreur">${this.erreurResync}</p>`:H}
      </section>
    `}};function Ye(e,t){return"piece"===t?`${Oe(e)} pièce${e>=2?"s":""}`:"g"===t?e>=1e3?`${Oe(e/1e3)} kg`:`${Oe(e)} g`:e>=1e3?`${Oe(e/1e3)} l`:`${Oe(e)} ml`}We.styles=o`
    .liste-magasins, .liste-rayons-magasin, .liste-recurrentes {
      list-style: none; margin: 0; padding: 0;
    }
    .magasin, .rayon-magasin, .recurrente {
      display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .magasin-onglet, .fusionner, .confirmer-fusion, .annuler-fusion,
    .monter-rayon-magasin, .descendre-rayon-magasin, .reprendre-apprentissage,
    .supprimer-recurrente, .ajouter-recurrente {
      min-height: 48px; min-width: 88px; border-radius: 8px; border: none; font-size: 0.9rem;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .magasin-onglet[aria-pressed='true'] {
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .magasin-onglet, .rayon-magasin-nom, .recurrente-nom { flex: 1 1 auto; }
    .marque-epingle { font-size: 0.8rem; color: var(--secondary-text-color); }
    .fiabilite { flex-basis: 100%; margin: 4px 0; font-size: 0.85rem; color: var(--secondary-text-color); }
    .erreur-fusion { color: var(--error-color, #b3261e); font-size: 0.9rem; margin: 8px 0 0; }
    .ajout-recurrente { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
    .champ-recurrente { flex: 1 1 140px; min-height: 48px; box-sizing: border-box; padding: 4px 8px; }
    .champ-jours { flex: 0 0 88px; min-height: 48px; box-sizing: border-box; padding: 4px 8px; }
    .agent-ticket, .taille-tickets { margin: 4px 0; color: var(--secondary-text-color); font-size: 0.9rem; }
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .en-attente { text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 0 0 8px; }
    .erreur { color: var(--error-color, #b3261e); font-size: 0.9rem; }
    .reessayer {
      min-height: 48px; width: 100%; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .section {
      margin: 0 0 20px; padding: 12px; border-radius: 8px; background: var(--secondary-background-color);
    }
    .titre { margin: 0 0 4px; font-size: 1rem; }
    .explication { margin: 0 0 8px; color: var(--secondary-text-color); font-size: 0.85rem; }
    .vide { color: var(--secondary-text-color); }
    .liste-rayons, .liste-emplacements { list-style: none; margin: 0; padding: 0; }
    .rayon, .emplacement {
      display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px;
      padding: 8px 0; border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .rayon:last-child, .emplacement:last-child { border-bottom: none; }
    .rayon-nom, .emplacement-nom { flex: 1; min-width: 0; }
    .emplacement-type { color: var(--secondary-text-color); font-size: 0.85rem; }
    .rayon-boutons { display: flex; gap: 8px; flex-shrink: 0; }
    .monter, .descendre {
      min-width: 48px; min-height: 48px; border-radius: 8px; border: none; font-size: 1.1rem;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .monter:disabled, .descendre:disabled { opacity: 0.4; }
    .resynchroniser {
      display: block; width: 100%; min-height: 48px; border-radius: 8px; border: none; font-size: 0.95rem;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .resynchroniser:disabled { opacity: 0.6; }
    .message-resync { color: var(--secondary-text-color); font-size: 0.85rem; margin: 8px 0 0; }
  `,e([de({attribute:!1})],We.prototype,"connexion",void 0),e([de({attribute:!1})],We.prototype,"file",void 0),e([de({attribute:!1})],We.prototype,"enAttente",void 0),e([he()],We.prototype,"rayons",void 0),e([he()],We.prototype,"emplacements",void 0),e([he()],We.prototype,"erreurChargement",void 0),e([he()],We.prototype,"magasins",void 0),e([he()],We.prototype,"magasinOuvert",void 0),e([he()],We.prototype,"parcours",void 0),e([he()],We.prototype,"fusionArmee",void 0),e([he()],We.prototype,"erreurFusion",void 0),e([he()],We.prototype,"recurrentes",void 0),e([he()],We.prototype,"saisieRecurrente",void 0),e([he()],We.prototype,"saisieJours",void 0),e([de({attribute:!1})],We.prototype,"agentTicket",void 0),e([de({attribute:!1})],We.prototype,"tailleTickets",void 0),e([he()],We.prototype,"resyncEnCours",void 0),e([he()],We.prototype,"messageResync",void 0),e([he()],We.prototype,"erreurResync",void 0),We=e([ce("home-stock-reglages")],We);const Ge={consumption:"Mangé",waste:"Jeté",expired:"Périmé"};let Ze=class extends ae{constructor(){super(...arguments),this.productId=null,this.produit=null,this.lot=null,this.portion=null,this.quantite=null,this.motif="consumption",this.partage=!1,this.partsTotal=2,this.partsMoi=1,this.erreur=null,this.enCours=!1,this.enAttenteEnvoi=!1,this.texteQuantite=""}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(!this.connexion||null===this.productId)return;const e=await this.connexion.appeler("home_stock/product/get",{product_id:this.productId});this.produit=e.produit??e.product,this.lot=e.next_batch,this.portion=e.suggested_portion,this.quantite="piece"===this.produit?.base_unit&&this.lot?1:null,this.texteQuantite=null===this.quantite?"":String(this.quantite)}saisirQuantite(e){this.texteQuantite=e;const t=Fe(e);if(!t.ok)return this.erreur="Quantité : ce n’est pas un nombre.",void(this.quantite=null);this.erreur=null,this.quantite=t.valeur}choisirRaccourci(e){this.erreur=null,this.quantite=e,this.texteQuantite=String(e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}async enregistrer(){if(this.enCours||!this.file||!this.lot||null===this.produit)return;if(null===this.quantite||!(this.quantite>0))return void(this.erreur="Quantité : donne un nombre supérieur à zéro.");const e=this.partage&&"consumption"===this.motif;if(e&&!(this.partsTotal>=1&&this.partsTotal<=24&&this.partsMoi>=0&&this.partsMoi<=this.partsTotal))return void(this.erreur=this.partsTotal>24?"On ne sert pas plus de 24 parts.":"On ne mange pas plus de parts qu’il n’en a été servi.");this.erreur=null,this.enCours=!0,this.enAttenteEnvoi=!1;const t={product_id:this.produit.id,quantity:this.quantite,reason:this.motif};this.quantite<=this.lot.remaining&&(t.batch_id=this.lot.id),e&&(t.parts_total=this.partsTotal,t.parts_mine=this.partsMoi);const i=this.file.ajouter("home_stock/stock/consume",t);this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile());const r=await i.sort;this.enCours=!1,"envoyee"===r?this.dispatchEvent(new CustomEvent("consommation-enregistree",{bubbles:!0,composed:!0})):"en-attente"===r&&(this.enAttenteEnvoi=!0)}rendreMotifs(){return B`
      <section class="motifs">
        ${Object.keys(Ge).map(e=>B`
          <button type="button" class="motif ${this.motif===e?"motif-actif":""}"
            @click=${()=>{this.motif=e}}>
            ${Ge[e]}
          </button>
        `)}
      </section>
    `}rendreParts(){return"consumption"!==this.motif?H:B`
      <section class="parts">
        <label class="partage-bascule">
          <input type="checkbox" .checked=${this.partage}
            @change=${e=>{this.partage=e.target.checked}} />
          Je partage
        </label>
        ${this.partage?B`
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
          </div>`:H}
      </section>
    `}render(){if(!this.produit)return H;if(!this.lot)return B`
        <section class="entete">
          <h2 class="nom">${this.produit.name}</h2>
        </section>
        <p class="plus-rien">Plus rien en stock.</p>
      `;const e=function(e,t,i){if(e<=0)return[];const r=[];"piece"===t?r.push({libelle:Ye(1,t),quantite:1}):null!==i&&i>0&&i<=e&&r.push({libelle:`1 portion (${Ye(i,t)})`,quantite:i}),"piece"!==t&&r.push({libelle:`La moitié (${Ye(e/2,t)})`,quantite:e/2}),r.push({libelle:`Tout le reste (${Ye(e,t)})`,quantite:e});const s=new Set;return r.filter(t=>t.quantite<=e&&!s.has(t.quantite)&&s.add(t.quantite))}(this.lot.remaining,this.produit.base_unit,this.portion);return B`
      <section class="entete">
        <h2 class="nom">${this.produit.name}</h2>
        <p class="reste">
          Reste ${t=this.lot.remaining,i=this.produit.base_unit,"piece"===i?`${Oe(t)} pièce${t>=2?"s":""}`:`${Oe(t)} ${i}`} sur le lot visé
          ${this.lot.best_before?B` — DLC ${function(e){const t=/^(\d{4})-(\d{2})-(\d{2})$/.exec(e);return t?`${t[3]}/${t[2]}/${t[1]}`:e}(this.lot.best_before)}`:H}
        </p>
      </section>

      <section class="raccourcis">
        ${e.map(e=>B`
          <button type="button" class="raccourci" @click=${()=>this.choisirRaccourci(e.quantite)}>
            ${e.libelle}
          </button>
        `)}
      </section>

      <label class="pave-label">
        Autre quantité
        <input class="pave" inputmode="decimal" .value=${this.texteQuantite}
          @input=${e=>this.saisirQuantite(e.target.value)} />
      </label>

      ${this.rendreMotifs()}
      ${this.rendreParts()}

      ${this.erreur?B`<p class="erreur">${this.erreur}</p>`:H}
      ${this.enAttenteEnvoi?B`
        <p class="en-attente">Pas encore envoyé — ça repartira dès que le réseau revient.</p>
      `:H}

      <button type="button" class="enregistrer" ?disabled=${this.enCours} @click=${this.enregistrer}>
        ${Ge[this.motif]}
      </button>
    `;var t,i}};Ze.styles=o`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .nom { margin: 0; font-size: 1.2rem; }
    .reste { margin: 2px 0; color: var(--secondary-text-color); }
    .plus-rien { color: var(--secondary-text-color); }
    .raccourcis { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
    .raccourci {
      min-height: 62px; min-width: 62px; flex: 1 1 auto; font-size: 1rem; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff); padding: 4px 8px;
    }
    .pave-label { display: block; margin: 8px 0; }
    .pave { min-height: 48px; font-size: 1rem; padding: 4px 8px; box-sizing: border-box; width: 100%; }
    .motifs { display: flex; gap: 8px; margin: 12px 0; }
    .motif {
      min-height: 62px; flex: 1 1 auto; font-size: 1rem; border-radius: 8px; border: none;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .motif-actif { background: var(--primary-color); color: var(--text-primary-color, #fff); }
    .parts { margin: 12px 0; padding: 8px; border-radius: 8px; background: var(--secondary-background-color); }
    .partage-bascule { display: flex; align-items: center; gap: 8px; min-height: 48px; }
    .partage-bascule input { width: 22px; height: 22px; }
    .compteurs { display: flex; gap: 12px; margin-top: 8px; }
    .compteur { flex: 1 1 auto; display: block; }
    .parts-total, .parts-moi { min-height: 48px; font-size: 1rem; padding: 4px 8px; box-sizing: border-box; width: 100%; }
    .erreur, .en-attente { color: var(--error-color, #b3261e); font-size: 0.9rem; }
    .enregistrer {
      display: block; width: 100%; min-height: 62px; font-size: 1.2rem; border-radius: 12px;
      border: none; background: var(--primary-color); color: var(--text-primary-color, #fff);
      margin-top: 12px;
    }
    .enregistrer:disabled { opacity: 0.5; }
  `,e([de({attribute:!1})],Ze.prototype,"connexion",void 0),e([de({attribute:!1})],Ze.prototype,"file",void 0),e([de({type:Number})],Ze.prototype,"productId",void 0),e([he()],Ze.prototype,"produit",void 0),e([he()],Ze.prototype,"lot",void 0),e([he()],Ze.prototype,"portion",void 0),e([he()],Ze.prototype,"quantite",void 0),e([he()],Ze.prototype,"motif",void 0),e([he()],Ze.prototype,"partage",void 0),e([he()],Ze.prototype,"partsTotal",void 0),e([he()],Ze.prototype,"partsMoi",void 0),e([he()],Ze.prototype,"erreur",void 0),e([he()],Ze.prototype,"enCours",void 0),e([he()],Ze.prototype,"enAttenteEnvoi",void 0),e([he()],Ze.prototype,"texteQuantite",void 0),Ze=e([ce("home-stock-consommation")],Ze);const Ke={day:14,week:12,month:12},Xe={day:"Jours",week:"Semaines",month:"Mois"};function et(e){return`${e.toFixed(2).replace(".",",")} €`}let tt=class extends ae{constructor(){super(...arguments),this.jour=null,this.serie=null,this.granularite="day",this.enCours=!1,this.seauSelectionne=null,this.detailOuvert=null,this.apercu=null,this.correctionArmee=null}connectedCallback(){super.connectedCallback(),this.chargerJour(),this.chargerSerie(this.granularite)}async chargerJour(e){this.connexion&&(this.jour=await this.connexion.appeler("home_stock/journal/day",e?{date:e}:{}))}async chargerSerie(e){if(this.connexion){this.enCours=!0;try{this.serie=await this.connexion.appeler("home_stock/journal/series",{granularity:e,count:Ke[e]})}finally{this.enCours=!1}}}async choisirGranularite(e){this.granularite=e,this.seauSelectionne=null,await this.chargerSerie(e)}async ouvrirSeau(e){"day"===this.granularite?(this.seauSelectionne=null,await this.chargerJour(e.label)):(this.jour=null,this.seauSelectionne=e)}partDeLaBarre(e,t){return t>0?e/t:0}rendreBarres(){const e=this.serie?.buckets??[],t=Math.max(0,...e.map(e=>e.kcal));return B`
      <div class="barres">
        ${e.map(e=>{const i=this.partDeLaBarre(e.kcal,t);return B`
            <button class="barre" data-part=${i}
                    style=${`--part: ${Math.round(100*i)}%`}
                    title=${`${e.label} — ${Math.round(e.kcal)} kcal`}
                    @click=${()=>this.ouvrirSeau(e)}>
              <span class="barre-remplissage"></span>
            </button>`})}
      </div>`}rendreGranularites(){return B`
      <nav class="granularites">
        ${Object.keys(Xe).map(e=>B`
          <button type="button" class="granularite ${this.granularite===e?"granularite-active":""}"
            @click=${()=>this.choisirGranularite(e)}>
            ${Xe[e]}
          </button>
        `)}
      </nav>
    `}rendreEntree(e){const t=null!==e.parts_total&&e.parts_total!==e.parts_mine,i=null!==(e.corrected_by??null),r=null!==(e.corrects_id??null),s=["entree","consumption"!==e.reason?"jete":"",i?"corrigee":"",r?"contrepassation":""].filter(Boolean).join(" ");return B`
      <li class=${s}>
        <button class="entree-ouvrir" @click=${()=>this.ouvrirDetail(e)}>
          <span class="entree-nom">${e.product_name}</span>
          <span class="entree-quantite">
            ${Oe(Math.abs(e.quantity))} ${e.base_unit}
          </span>
          ${t?B`
            <span class="entree-parts">${e.parts_mine??0}/${e.parts_total}</span>
          `:H}
          <span class="entree-kcal">${null===e.kcal?"—":`${Math.round(e.kcal)} kcal`}</span>
        </button>
        ${this.detailOuvert===e.id?this.rendreDetail():H}
      </li>
    `}async ouvrirDetail(e){if(this.detailOuvert!==e.id){if(this.detailOuvert=e.id,this.apercu=null,this.correctionArmee=null,this.connexion)try{this.apercu=await this.connexion.appeler("home_stock/movement/correction_preview",{movement_id:e.id})}catch{this.apercu=null}}else this.detailOuvert=null}ecrire(e,t){this.file&&(this.file.ajouter(e,t),this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0})),this.file.rejouer())}confirmerCorrection(){const e=this.correctionArmee;e&&("mouvement"===e.cible?this.ecrire("home_stock/movement/correct",{movement_id:e.id}):this.ecrire("home_stock/meal/correct",{meal_id:e.id}),this.correctionArmee=null,this.detailOuvert=null)}rendreDetail(){const e=this.apercu;if(!e)return B`<div class="detail"><p>Chargement…</p></div>`;const t=e.batch_entered_at?` et remet ${Oe(e.quantity)} ${e.base_unit??""} dans le lot du ${e.batch_entered_at.slice(0,10)}`:"",i=[null===e.kcal?null:`${Math.round(e.kcal)} kcal`,null===e.cost?null:et(e.cost)].filter(Boolean).join(", ");return B`
      <div class="detail">
        <p class="annonce">${`Annule ${Oe(e.quantity)} ${e.base_unit??""} de ${e.product_name??""}`+(i?` — ${i}`:"")+t+"."}</p>
        ${e.refusal?B`<p class="refus">${e.refusal}</p>`:H}
        ${this.correctionArmee?B`
          <button class="confirmer-correction" @click=${this.confirmerCorrection}>
            Confirmer
          </button>
          <button class="annuler-correction"
            @click=${()=>{this.correctionArmee=null}}>Annuler</button>
        `:B`
          ${e.correctable?B`
            <button class="corriger" @click=${()=>{this.correctionArmee={cible:"mouvement",id:e.movement_id}}}>Corriger</button>
          `:H}
          ${!e.correctable&&e.meal_id?B`
            <button class="corriger-repas" @click=${()=>{this.correctionArmee={cible:"repas",id:e.meal_id}}}>Corriger le repas</button>
          `:H}
        `}
      </div>
    `}rendreJour(){const e=this.jour;return e?B`
      <section class="jour">
        <h2 class="titre-jour">${e.food_day}</h2>
        ${0===e.entries.length?B`
          <p class="vide">Rien de déclaré ce jour-là.</p>
        `:B`
          <ul class="entrees">
            ${e.entries.map(e=>this.rendreEntree(e))}
          </ul>
        `}
        <p class="total-kcal">${Math.round(e.totals.kcal)} kcal</p>
        <p class="total-cout">
          ${et(e.totals.cost)}
          ${e.totals.waste_cost>0?B` — dont ${et(e.totals.waste_cost)} jeté`:H}
        </p>
        ${e.totals.unvalued>0?B`
          <p class="non-chiffre">${e.totals.unvalued} sortie(s) sans calories connues.</p>
        `:H}
      </section>
    `:H}rendreSeauTotaux(){const e=this.seauSelectionne;return e?B`
      <section class="jour">
        <h2 class="titre-jour">${e.label}</h2>
        <p class="total-kcal">${Math.round(e.kcal)} kcal</p>
        <p class="total-cout">
          ${et(e.cost)}
          ${e.waste_cost>0?B` — dont ${et(e.waste_cost)} jeté`:H}
        </p>
      </section>
    `:H}render(){return B`
      <h1 class="titre">Journal</h1>
      ${this.rendreGranularites()}
      ${this.rendreBarres()}
      ${"day"===this.granularite?this.rendreJour():this.rendreSeauTotaux()}
    `}};function it(e){return e.normalize("NFD").replace(/[̀-ͯ]/g,"").replace(/œ/g,"oe").replace(/æ/g,"ae").toLowerCase()}tt.styles=o`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .titre { margin: 0 0 8px; font-size: 1.2rem; }
    .granularites { display: flex; gap: 8px; margin-bottom: 8px; }
    .granularite {
      flex: 1 1 auto; min-height: 48px; border-radius: 8px; border: none; font-size: 0.9rem;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .granularite-active { background: var(--primary-color); color: var(--text-primary-color, #fff); }
    .entree-ouvrir {
      display: flex; width: 100%; gap: 8px; align-items: baseline; min-height: 48px;
      border: none; background: transparent; color: inherit; font: inherit;
      text-align: left; padding: 0;
    }
    .corrigee .entree-nom, .corrigee .entree-quantite { text-decoration: line-through; }
    .contrepassation { color: var(--secondary-text-color); }
    .detail {
      margin: 4px 0 8px; padding: 8px; border-radius: 8px;
      background: var(--secondary-background-color);
    }
    .annonce { margin: 0 0 8px; }
    .refus { margin: 0 0 8px; color: var(--secondary-text-color); font-size: 0.9rem; }
    .corriger, .corriger-repas, .confirmer-correction, .annuler-correction {
      display: block; width: 100%; min-height: 48px; border-radius: 8px; border: none;
      margin-top: 8px; font-size: 1rem;
    }
    .corriger, .corriger-repas, .confirmer-correction {
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .annuler-correction {
      background: var(--card-background-color, #fff); color: var(--primary-text-color);
    }
    /* La cible tactile de .barre est fixe (colonne pleine hauteur ici,
       ligne pleine largeur sous 700 px) — jamais la grandeur du seau, qui ne
       viendrait qu'agrandir les gros jours et rétrécir les petits sous les
       48 px. Quatorze seaux sur 412 px ne tiennent pas en colonnes larges de
       48 px (14 x 48 > 372 px de contenu disponible) : sous 700 px, le
       graphe passe donc en liste de lignes empilées, chacune pleine largeur,
       où c'est la largeur du remplissage qui porte la valeur. */
    .barres {
      display: flex; gap: 4px; margin: 8px 0 16px;
      padding: 8px; border-radius: 8px; background: var(--secondary-background-color); box-sizing: border-box;
    }
    .barre {
      flex: 1 1 auto; min-width: 12px; height: 120px; min-height: 48px; box-sizing: border-box;
      display: flex; align-items: flex-end; border: none; border-radius: 4px; background: transparent; padding: 0;
    }
    .barre-remplissage {
      display: block; width: 100%; height: var(--part); min-height: 4px;
      border-radius: 4px 4px 0 0; background: var(--primary-color); pointer-events: none;
    }
    @media (max-width: 700px) {
      .barres { flex-direction: column; }
      .barre { flex: none; width: 100%; height: auto; min-height: 48px; align-items: stretch; }
      .barre-remplissage { width: var(--part); height: 100%; min-width: 4px; min-height: 0; border-radius: 0 4px 4px 0; }
    }
    .jour { margin-top: 8px; }
    .titre-jour { margin: 0 0 8px; font-size: 1rem; color: var(--secondary-text-color); }
    .entrees { list-style: none; margin: 0 0 8px; padding: 0; }
    .entree {
      display: flex; align-items: center; flex-wrap: wrap; gap: 8px; min-height: 48px;
      padding: 8px 0; border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .entree-nom { flex: 1 1 auto; }
    .entree-quantite, .entree-kcal { color: var(--secondary-text-color); font-size: 0.85rem; }
    .entree-parts {
      font-size: 0.8rem; padding: 2px 6px; border-radius: 999px;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .entree.jete { color: var(--error-color, #b3261e); }
    .vide { color: var(--secondary-text-color); }
    .total-kcal { margin: 4px 0 0; font-size: 1.1rem; font-weight: 600; }
    .total-cout { margin: 2px 0; color: var(--secondary-text-color); }
    .non-chiffre { color: var(--error-color, #b3261e); font-size: 0.85rem; }
  `,e([de({attribute:!1})],tt.prototype,"connexion",void 0),e([he()],tt.prototype,"jour",void 0),e([he()],tt.prototype,"serie",void 0),e([he()],tt.prototype,"granularite",void 0),e([he()],tt.prototype,"enCours",void 0),e([he()],tt.prototype,"seauSelectionne",void 0),e([de({attribute:!1})],tt.prototype,"file",void 0),e([he()],tt.prototype,"detailOuvert",void 0),e([he()],tt.prototype,"apercu",void 0),e([he()],tt.prototype,"correctionArmee",void 0),tt=e([ce("home-stock-journal")],tt);let rt=class extends ae{constructor(){super(...arguments),this.enAttente=!1,this.recettes=[],this.filtre="",this.fiches=null,this.chercheEnLigne=!1,this.message=""}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(!this.connexion)return;const e=await this.connexion.appeler("home_stock/recipes/list",{});this.recettes=e.recipes??[]}get recettesFiltrees(){if(!this.filtre.trim())return this.recettes;const e=it(this.filtre.trim());return this.recettes.filter(t=>it(t.name).includes(e))}ouvrir(e){this.dispatchEvent(new CustomEvent("recette-ouverte",{detail:{recipe_id:e.id},bubbles:!0,composed:!0}))}async chercherAilleurs(){if(this.connexion&&!this.enAttente){this.chercheEnLigne=!0,this.message="";try{const e=await this.connexion.appeler("home_stock/recipe/search_external",{query:this.filtre.trim()});this.fiches=e.hits??[],this.fiches.length||(this.message=!1===e.reachable?"La source de recettes est injoignable pour le moment.":"Aucune recette trouvée à la source.")}finally{this.chercheEnLigne=!1}}}async importer(e){if(!this.connexion)return;const t=await this.connexion.appeler("home_stock/recipe/import_external",{source_ref:e.source_ref});this.message=t.adapted?`« ${e.name} » a été importée et adaptée en français.`:`« ${e.name} » a été importée. Elle est en anglais : à relire.`,this.fiches=null,await this.charger()}async marquerRelue(e){this.file&&(this.file.ajouter("home_stock/recipe/update",{recipe_id:e.id,fields:{needs_review:0}}),this.recettes=this.recettes.map(t=>t.id===e.id?{...t,needs_review:0}:t))}rendreRecette(e){return B`
      <button class="recette" @click=${()=>this.ouvrir(e)}>
        <span class="recette-nom">${e.name}</span>
        <span class="badges">
          ${e.needs_review?B`<span class="badge relire">à relire</span>`:H}
          ${e.unmatched_count>0?B`<span class="badge manque">${e.unmatched_count} non apparié${e.unmatched_count>1?"s":""}</span>`:H}
        </span>
      </button>
    `}rendreFiche(e){return B`
      <button class="fiche" @click=${()=>this.importer(e)}>
        <span class="fiche-nom">${e.name}</span>
        <span class="fiche-meta">${[e.category,e.area].filter(Boolean).join(" · ")}</span>
      </button>
    `}render(){const e=this.recettesFiltrees;return B`
      <div class="entete">
        <input class="recherche" type="search" placeholder="Chercher une recette"
               .value=${this.filtre}
               @input=${e=>{this.filtre=e.target.value}} />
        <button class="ailleurs" ?disabled=${this.enAttente||this.chercheEnLigne}
                @click=${()=>this.chercherAilleurs()}>
          ${this.chercheEnLigne?"Recherche…":"Chercher ailleurs"}
        </button>
      </div>

      ${this.message?B`<p class="message">${this.message}</p>`:H}

      ${this.fiches?B`<section class="fiches">
            <h2>Trouvées à la source</h2>
            ${this.fiches.map(e=>this.rendreFiche(e))}
          </section>`:H}

      ${e.length?B`<section class="liste">
            ${e.map(e=>this.rendreRecette(e))}
          </section>`:B`<p class="vide">${this.filtre?"Aucune recette ne correspond.":"Aucune recette pour le moment."}</p>`}
    `}};function st(e,t=0){const i=Math.max(0,e);return{restant:i,enMarche:i>0,termine:0===i,duree:i}}function nt(e,t){if(!e.enMarche)return e;const i=Math.max(0,e.restant-Math.max(0,t));return{...e,restant:i,enMarche:i>0,termine:0===i}}function ot(e){const t=Math.max(0,e);return{restant:t,enMarche:!1,termine:!1,duree:t}}rt.styles=o`
    :host { display: block; padding: 12px; color: var(--primary-text-color); }
    .entete { display: flex; gap: 8px; margin-bottom: 12px; }
    .recherche {
      flex: 1; min-height: 48px; padding: 0 12px; font-size: 1rem;
      border: 1px solid var(--divider-color); border-radius: 8px;
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .ailleurs {
      min-height: 48px; padding: 0 16px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--divider-color);
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .ailleurs[disabled] { opacity: 0.5; cursor: default; }
    .message { margin: 8px 0; }
    .liste, .fiches { display: flex; flex-direction: column; gap: 8px; }
    h2 { font-size: 1rem; margin: 12px 0 4px; }
    .recette, .fiche {
      display: flex; justify-content: space-between; align-items: center;
      gap: 8px; min-height: 48px; padding: 8px 12px; text-align: left;
      border: 1px solid var(--divider-color); border-radius: 8px; cursor: pointer;
      background: var(--card-background-color); color: var(--primary-text-color);
      font-size: 1rem;
    }
    .recette-nom, .fiche-nom { flex: 1; }
    .badges { display: flex; gap: 6px; }
    .badge {
      padding: 2px 8px; border-radius: 999px; font-size: 0.8rem; white-space: nowrap;
    }
    /* Le repli est un orange FONCÉ, pas celui de Material : blanc sur
       #b26a00 ne donne que 4,24:1, sous le seuil de 4,5:1 que
       verifier-rendu.mjs applique. #8a5300 monte à 6,3:1. On corrige la
       couleur, jamais le seuil. */
    .relire { background: var(--warning-color, #8a5300); color: #fff; }
    .manque { background: var(--error-color, #a01b1b); color: #fff; }
    .fiche-meta { opacity: 0.75; font-size: 0.85rem; }
    .vide { opacity: 0.75; }
    @media (max-width: 700px) {
      .entete { flex-direction: column; }
    }
  `,e([de({attribute:!1})],rt.prototype,"connexion",void 0),e([de({attribute:!1})],rt.prototype,"file",void 0),e([de({type:Boolean})],rt.prototype,"enAttente",void 0),e([he()],rt.prototype,"recettes",void 0),e([he()],rt.prototype,"filtre",void 0),e([he()],rt.prototype,"fiches",void 0),e([he()],rt.prototype,"chercheEnLigne",void 0),e([he()],rt.prototype,"message",void 0),rt=e([ce("home-stock-recettes")],rt);let at=class extends ae{constructor(){super(...arguments),this.vue=null,this.page=0,this.ingredientsOuverts=!1,this.minuteurs={},this._wakeLock=null}connectedCallback(){super.connectedCallback(),this.charger(),this.garderEveille(),this._tic=setInterval(()=>this.avancerLesMinuteurs(),1e3)}disconnectedCallback(){super.disconnectedCallback(),this._tic&&clearInterval(this._tic),this.relacherEveil()}async charger(){this.connexion&&void 0!==this.recipeId&&(this.vue=await this.connexion.appeler("home_stock/recipe/get",{recipe_id:this.recipeId}))}async garderEveille(){const e=navigator?.wakeLock;if(e?.request)try{this._wakeLock=await e.request("screen")}catch{this._wakeLock=null}}async relacherEveil(){try{await(this._wakeLock?.release())}catch{}this._wakeLock=null}get nombreDePages(){return(this.vue?.steps.length??0)+1}get peutReculer(){return this.page>0}get peutAvancer(){return this.page<this.nombreDePages-1}reculer(){this.peutReculer&&(this.page-=1)}avancerPage(){this.peutAvancer&&(this.page+=1)}ouvrirIngredients(){this.ingredientsOuverts=!0}fermerIngredients(){this.ingredientsOuverts=!1}fermer(){this.dispatchEvent(new CustomEvent("recette-fermee",{bubbles:!0,composed:!0}))}validerRepas(){void 0!==this.mealId&&this.dispatchEvent(new CustomEvent("valider-repas",{detail:{meal_id:this.mealId},bubbles:!0,composed:!0}))}basculerMinuteur(e){if(null===e.timer_seconds)return;const t=this.minuteurs[e.id];this.minuteurs={...this.minuteurs,[e.id]:t&&(t.enMarche||t.termine)?ot(e.timer_seconds):st(e.timer_seconds)}}avancerLesMinuteurs(){const e=Object.entries(this.minuteurs);e.some(([,e])=>e.enMarche)&&(this.minuteurs=Object.fromEntries(e.map(([e,t])=>[e,nt(t,1)])))}libelleQuantite(e){return e.display_amount?e.display_amount:null===e.amount?"":Ie(e.amount,e.product_base_unit??"g",e.measure_name,e.packaging_name)}async apparier(e,t){if(this.file&&(this.file.ajouter("home_stock/recipe/ingredient/match",{ingredient_id:e.id,product_id:t,state:"confirmed",create_alias:!0}),this.file.rejouer?.(),this.vue)){const i=e.candidates?.find(e=>e.product_id===t)?.name??null;this.vue={...this.vue,ingredients:this.vue.ingredients.map(r=>r.id===e.id?{...r,match_state:"confirmed",product_id:t,product_name:i,candidates:[]}:r)}}}rendreIngredients(){const e=this.vue?.ingredients??[];return B`
      <section class="ingredients">
        <h2>Ingrédients</h2>
        <ul>
          ${e.map(e=>B`
            <li class="ingredient ${"unmatched"===e.match_state?"a-la-main":""}">
              <span class="quantite">${this.libelleQuantite(e)}</span>
              <span class="ingredient-nom">${e.product_name??e.raw_text}</span>
              ${"unmatched"===e.match_state?B`<span class="mention">à sortir à la main</span>`:H}
              ${"unmatched"===e.match_state&&e.candidates?.length?B`<span class="candidats">
                    ${e.candidates.map(t=>B`
                      <button class="candidat"
                              @click=${()=>this.apparier(e,t.product_id)}>
                        ${t.name}
                      </button>`)}
                  </span>`:H}
            </li>`)}
        </ul>
        <button class="fermer-ingredients" @click=${()=>this.fermerIngredients()}>
          Revenir à la recette
        </button>
      </section>
    `}rendreCouverture(){const e=this.vue.recipe;return B`
      <section class="couverture">
        ${e.image_url?B`<img class="image" src=${e.image_url} alt="" />`:H}
        <h1>${e.name}</h1>
        <p class="meta">
          ${e.total_minutes?B`<span class="duree">⏱ ${e.total_minutes} min</span>`:H}
          <span class="parts">🔥 ${e.servings} part${e.servings>1?"s":""}</span>
          ${e.utensils?B`<span class="ustensiles">🍳 ${e.utensils}</span>`:H}
        </p>
        ${e.summary?B`<p class="accroche">${e.summary}</p>`:H}
      </section>
    `}rendrePuce(e){const t=this.minuteurs[e.id];return B`
      <li class="puce">
        <span class="puce-texte">${e.text}</span>
        ${null!==e.timer_label&&null!==e.timer_seconds?B`<button class="minuteur ${t?.termine?"termine":""}"
                         @click=${()=>this.basculerMinuteur(e)}>
              ${e.timer_label} ·
              ${function(e){const t=Math.max(0,Math.round(e)),i=Math.floor(t/3600),r=Math.floor(t%3600/60),s=t%60,n=e=>String(e).padStart(2,"0");return i>0?`${i}:${n(r)}:${n(s)}`:`${r}:${n(s)}`}(t?t.restant:e.timer_seconds)}
            </button>`:H}
      </li>
    `}rendreEtape(e){return B`
      <section class="etape">
        ${e.image_url?B`<img class="image" src=${e.image_url} alt="" />`:H}
        <h2>${e.title??`Étape ${e.position}`}</h2>
        <ol class="puces">${e.instructions.map(e=>this.rendrePuce(e))}</ol>
      </section>
    `}render(){if(!this.vue)return B`<p class="chargement">Chargement…</p>`;if(this.ingredientsOuverts)return this.rendreIngredients();const e=!this.peutAvancer;return B`
      ${0===this.page?this.rendreCouverture():this.rendreEtape(this.vue.steps[this.page-1])}

      <nav class="barre">
        <button class="precedent" ?disabled=${!this.peutReculer}
                @click=${()=>this.reculer()}>Précédent</button>
        <button class="ingredients-bouton" @click=${()=>this.ouvrirIngredients()}>
          Ingrédients
        </button>
        <span class="position">${this.page+1} / ${this.nombreDePages}</span>
        ${e&&void 0!==this.mealId?B`<button class="cuisine" @click=${()=>this.validerRepas()}>
              J'ai cuisiné
            </button>`:B`<button class="suivant" ?disabled=${!this.peutAvancer}
                         @click=${()=>this.avancerPage()}>Suivant</button>`}
      </nav>
    `}};at.styles=o`
    :host {
      display: block; padding: 16px; font-size: 1.25rem;
      color: var(--primary-text-color);
    }
    .image { width: 100%; max-height: 40vh; object-fit: cover; border-radius: 12px; }
    h1 { font-size: 1.8rem; margin: 12px 0 4px; }
    h2 { font-size: 1.5rem; margin: 12px 0 8px; }
    .meta { display: flex; flex-wrap: wrap; gap: 12px; opacity: 0.85; margin: 4px 0; }
    .accroche { opacity: 0.9; }
    .puces { display: flex; flex-direction: column; gap: 12px; padding-left: 1.2em; }
    .puce { line-height: 1.5; }
    .minuteur {
      display: block; margin-top: 8px; min-height: 48px; padding: 0 16px;
      font-size: 1.1rem; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--divider-color);
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .minuteur.termine { background: var(--error-color, #a01b1b); color: #fff; }
    .ingredients ul { list-style: none; padding: 0; display: flex;
                      flex-direction: column; gap: 12px; }
    .ingredient { display: flex; flex-wrap: wrap; gap: 10px;
                  align-items: baseline; min-height: 48px; }
    .quantite { font-weight: 600; min-width: 6em; }
    .a-la-main .mention { opacity: 0.8; font-size: 0.9rem; font-style: italic; }
    .candidats { display: flex; flex-wrap: wrap; gap: 6px; width: 100%; }
    .candidat {
      min-height: 48px; padding: 0 12px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--divider-color); font-size: 0.95rem;
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .barre {
      display: flex; gap: 8px; align-items: center; margin-top: 20px;
      position: sticky; bottom: 0; padding: 8px 0;
      background: var(--card-background-color);
    }
    .barre button, .fermer-ingredients {
      min-height: 48px; padding: 0 16px; font-size: 1rem; border-radius: 8px;
      cursor: pointer; border: 1px solid var(--divider-color);
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .barre button[disabled] { opacity: 0.4; cursor: default; }
    .position { margin-left: auto; opacity: 0.75; }
    .cuisine { background: var(--primary-color, #03a9f4); color: #fff; }
    @media (max-width: 700px) {
      :host { font-size: 1.15rem; }
      .quantite { min-width: 4.5em; }
    }
  `,e([de({attribute:!1})],at.prototype,"connexion",void 0),e([de({attribute:!1})],at.prototype,"file",void 0),e([de({type:Number})],at.prototype,"recipeId",void 0),e([de({type:Number})],at.prototype,"mealId",void 0),e([he()],at.prototype,"vue",void 0),e([he()],at.prototype,"page",void 0),e([he()],at.prototype,"ingredientsOuverts",void 0),e([he()],at.prototype,"minuteurs",void 0),at=e([ce("home-stock-recette")],at);const lt={ok:"prêt",short:"stock insuffisant",unmatched:"produit non identifié",unquantified:"quantité inconnue",ignored:"ignoré"};let ct=class extends ae{constructor(){super(...arguments),this.preview=null,this.partsMangees=1,this.partage=!1,this.partsTotal=4,this.partsMoi=1,this.retirees=[],this.arme=!1,this.enCours=!1,this.enAttenteEnvoi=!1,this.erreur=null}connectedCallback(){super.connectedCallback(),this.simuler()}async simuler(){this.connexion&&void 0!==this.mealId&&(this.preview=await this.connexion.appeler("home_stock/meal/preview",{meal_id:this.mealId,skip_ingredient_ids:this.retirees}))}async retirerLigne(e){this.retirees=[...this.retirees,e.ingredient_id],this.arme=!1,await this.simuler()}get bloque(){return(this.preview?.blocking.length??0)>0}valider(){this.bloque||this.enCours||(this.arme?this.envoyer():this.arme=!0)}annuler(){this.arme=!1}async envoyer(){if(!this.file||void 0===this.mealId||this.enCours)return;const e=this.partsMangees;if(null===e||e<0)return void(this.erreur="Parts mangées : donne un nombre positif ou zéro.");if(this.preview?.dish&&e>this.preview.dish.parts)return void(this.erreur="On ne mange pas plus de parts que le plat n’en fait.");if(this.partage&&!(this.partsTotal>=1&&this.partsTotal<=24&&this.partsMoi>=0&&this.partsMoi<=this.partsTotal))return void(this.erreur=this.partsTotal>24?"On ne sert pas plus de 24 parts.":"On ne mange pas plus de parts qu’il n’en a été servi.");this.erreur=null,this.enCours=!0,this.arme=!1;const t={meal_id:this.mealId,portions_eaten:e,skip_ingredient_ids:this.retirees};this.partage&&(t.parts_total=this.partsTotal,t.parts_mine=this.partsMoi);const i=this.file.ajouter("home_stock/meal/validate",t);this.file.rejouer?.();const r=await i.sort;this.enCours=!1,this.enAttenteEnvoi="en-attente"===r,"refusee"!==r?this.dispatchEvent(new CustomEvent("repas-valide",{detail:{meal_id:this.mealId},bubbles:!0,composed:!0})):this.erreur="La validation a été refusée."}rendreLigne(e,t){return B`
      <li class="ligne statut-${e.status}">
        <span class="ligne-quantite">${e.label}</span>
        <span class="ligne-nom">${e.product_name??e.raw_text}</span>
        <span class="ligne-statut">${lt[e.status]}</span>
        ${t?B`<button class="retirer" @click=${()=>this.retirerLigne(e)}>
              Retirer
            </button>`:H}
      </li>
    `}rendreValeur(e,t=""){return"number"!=typeof e?"—":`${Oe(e)}${t}`}rendrePlat(){const e=this.preview?.dish;return e?B`
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
    `:H}rendreParts(){return B`
      <section class="parts">
        <label class="partage-bascule">
          <input type="checkbox" .checked=${this.partage}
            @change=${e=>{this.partage=e.target.checked}} />
          Je partage
        </label>
        ${this.partage?B`
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
          </div>`:H}
      </section>
    `}render(){if(!this.preview)return B`<p class="chargement">Chargement…</p>`;const e=this.preview;return B`
      <h1>${e.recipe?.name??"Repas"}</h1>

      <section class="sorties">
        <h2>Ce qui sort du stock</h2>
        <ul>${e.lines.map(e=>this.rendreLigne(e,!0))}</ul>
      </section>

      ${e.by_hand.length?B`<section class="a-la-main">
            <h2>À sortir à la main</h2>
            <ul>${e.by_hand.map(e=>this.rendreLigne(e,!1))}</ul>
          </section>`:H}

      ${this.rendrePlat()}

      <label class="mangees">
        Parts mangées
        <input class="parts-mangees" type="text" inputmode="decimal"
          .value=${null===this.partsMangees?"":Oe(this.partsMangees)}
          @input=${e=>{const t=Fe(e.target.value);t.ok&&(this.partsMangees=t.valeur)}} />
      </label>

      ${this.rendreParts()}

      ${this.bloque?B`<p class="blocage">
            Il manque du stock pour au moins un ingrédient : ajustez la quantité
            ou retirez ces lignes avant de valider.
          </p>`:H}

      ${this.erreur?B`<p class="erreur">${this.erreur}</p>`:H}
      ${this.enAttenteEnvoi?B`<p class="en-attente">Enregistré, en attente de réseau.</p>`:H}

      ${this.arme?B`<p class="sans-retour">
            Cette validation ne s'annule pas : les mouvements écrits restent au
            journal.
          </p>`:H}

      <div class="actions">
        <button class="valider" ?disabled=${this.bloque||this.enCours}
                @click=${()=>this.valider()}>
          ${this.arme?"Confirmer la validation":"Valider le repas"}
        </button>
        ${this.arme?B`<button class="annuler" @click=${()=>this.annuler()}>Annuler</button>`:H}
      </div>
    `}};ct.styles=o`
    :host { display: block; padding: 12px; color: var(--primary-text-color); }
    h1 { font-size: 1.4rem; margin: 0 0 12px; }
    h2 { font-size: 1.05rem; margin: 16px 0 6px; }
    ul { list-style: none; padding: 0; display: flex; flex-direction: column; gap: 6px; }
    .ligne {
      display: flex; align-items: center; gap: 10px; min-height: 48px;
      padding: 4px 8px; border-radius: 8px;
      border: 1px solid var(--divider-color);
    }
    .ligne-quantite { font-weight: 600; min-width: 6em; }
    .ligne-nom { flex: 1; }
    .ligne-statut { opacity: 0.75; font-size: 0.85rem; }
    .statut-short { border-color: var(--error-color, #a01b1b); }
    .retirer, .valider, .annuler {
      min-height: 48px; padding: 0 16px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--divider-color); font-size: 1rem;
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .valider { background: var(--primary-color, #03a9f4); color: #fff; }
    .valider[disabled] { opacity: 0.4; cursor: default; }
    .plat dl { display: flex; flex-wrap: wrap; gap: 12px; margin: 0; }
    .plat dt { opacity: 0.75; font-size: 0.85rem; }
    .plat dd { margin: 0; font-weight: 600; }
    .mangees { display: flex; flex-direction: column; gap: 4px; margin-top: 16px; }
    .parts-mangees { min-height: 48px; font-size: 1rem; padding: 4px 8px;
                     box-sizing: border-box; }
    .partage-bascule { display: flex; align-items: center; gap: 8px; min-height: 48px; }
    .partage-bascule input { width: 22px; height: 22px; }
    .compteurs { display: flex; gap: 12px; }
    .parts-total, .parts-moi { min-height: 48px; font-size: 1rem; padding: 4px 8px;
                               box-sizing: border-box; width: 100%; }
    .blocage, .erreur { color: var(--error-color, #a01b1b); }
    .sans-retour { font-weight: 600; }
    .actions { display: flex; gap: 8px; margin-top: 16px; }
    @media (max-width: 700px) {
      .ligne { flex-wrap: wrap; }
      .compteurs { flex-direction: column; }
    }
  `,e([de({attribute:!1})],ct.prototype,"connexion",void 0),e([de({attribute:!1})],ct.prototype,"file",void 0),e([de({type:Number})],ct.prototype,"mealId",void 0),e([he()],ct.prototype,"preview",void 0),e([he()],ct.prototype,"partsMangees",void 0),e([he()],ct.prototype,"partage",void 0),e([he()],ct.prototype,"partsTotal",void 0),e([he()],ct.prototype,"partsMoi",void 0),e([he()],ct.prototype,"retirees",void 0),e([he()],ct.prototype,"arme",void 0),e([he()],ct.prototype,"enCours",void 0),e([he()],ct.prototype,"enAttenteEnvoi",void 0),e([he()],ct.prototype,"erreur",void 0),ct=e([ce("home-stock-validation")],ct);const ut=[["breakfast","Petit-déjeuner"],["lunch","Déjeuner"],["dinner","Dîner"],["snack","En-cas"]],pt=["dimanche","lundi","mardi","mercredi","jeudi","vendredi","samedi"];function dt(e,t){const i=new Date(`${e}T12:00:00Z`);return i.setUTCDate(i.getUTCDate()+t),i.toISOString().slice(0,10)}function ht(e){const t=new Date(`${e}T12:00:00Z`);return`${pt[t.getUTCDay()]} ${t.getUTCDate()}`}let mt=class extends ae{constructor(){super(...arguments),this.large=!1,this.debut=(new Date).toISOString().slice(0,10),this.repas=[],this.manquants=[],this.armeAnnulation=null,this.message=null}connectedCallback(){super.connectedCallback(),this.charger()}get jours(){const e=this.large?7:1;return Array.from({length:e},(e,t)=>dt(this.debut,t))}async charger(){if(!this.connexion)return;const e=this.jours,t=await this.connexion.appeler("home_stock/meals/list",{start:e[0],end:e[e.length-1]});this.repas=t.meals??[]}async allerA(e){this.debut=dt(this.debut,this.large?7*e:e),this.armeAnnulation=null,await this.charger()}repasDe(e,t){return this.repas.filter(i=>i.day===e&&i.slot_key===t).sort((e,t)=>e.position-t.position)}async poser(e,t){this.file&&(this.file.ajouter("home_stock/meal/plan",{day:e,slot_key:t,note:"Repas",servings:1}),this.file.rejouer?.(),await this.charger())}async deplacer(e,t,i){this.file&&("done"!==e.state?(this.message=null,this.file.ajouter("home_stock/meal/move",{meal_id:e.id,day:t,slot_key:i}),this.file.rejouer?.(),await this.charger()):this.message="Un repas validé ne se déplace pas : ses mouvements portent une date figée.")}async annuler(e){this.armeAnnulation===e.id?this.file&&(this.armeAnnulation=null,this.file.ajouter("home_stock/meal/cancel",{meal_id:e.id}),this.file.rejouer?.(),await this.charger()):this.armeAnnulation=e.id}ouvrirRecette(e){null!==e.recipe_id&&this.dispatchEvent(new CustomEvent("recette-ouverte",{detail:{recipe_id:e.recipe_id,meal_id:e.id},bubbles:!0,composed:!0}))}ouvrirValidation(e){"done"!==e.state&&this.dispatchEvent(new CustomEvent("valider-repas",{detail:{meal_id:e.id},bubbles:!0,composed:!0}))}nomDe(e){return e.recipe_name??e.product_name??e.note??"Repas"}rendreRepas(e){return B`
      <div class="repas etat-${e.state}">
        <button class="repas-nom" @click=${()=>this.ouvrirRecette(e)}>
          ${this.nomDe(e)}
        </button>
        ${"done"===e.state?B`<span class="valide">validé</span>`:B`
            <button class="valider-repas" @click=${()=>this.ouvrirValidation(e)}>
              Valider
            </button>
            <button class="annuler-repas" @click=${()=>this.annuler(e)}>
              ${this.armeAnnulation===e.id?"Confirmer":"Annuler"}
            </button>`}
      </div>
    `}rendreCase(e,t){const i=this.repasDe(e,t);return B`
      <div class="case">
        ${i.map(e=>this.rendreRepas(e))}
        <button class="poser" @click=${()=>this.poser(e,t)}>+</button>
      </div>
    `}render(){const e=this.jours;return B`
      <div class="entete">
        <button class="precedent-jour" @click=${()=>this.allerA(-1)}>Précédent</button>
        <span class="periode">${this.large?`${ht(e[0])} — ${ht(e[e.length-1])}`:ht(e[0])}</span>
        <button class="suivant-jour" @click=${()=>this.allerA(1)}>Suivant</button>
      </div>

      ${this.message?B`<p class="message">${this.message}</p>`:H}
      ${this.manquants.length?B`<p class="manquants">${this.manquants.length} produit${this.manquants.length>1?"s":""} à acheter</p>`:H}

      <div class="grille ${this.large?"large":"etroit"}">
        ${this.large?B`<div class="ligne-jours">
              <span class="coin"></span>
              ${e.map(e=>B`<span class="jour">${ht(e)}</span>`)}
            </div>`:H}
        ${ut.map(([t,i])=>B`
          <div class="ligne-creneau">
            <span class="creneau">${i}</span>
            ${e.map(e=>this.rendreCase(e,t))}
          </div>`)}
      </div>
    `}};mt.styles=o`
    :host { display: block; padding: 12px; color: var(--primary-text-color); }
    .entete { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
    .periode { flex: 1; text-align: center; font-weight: 600; }
    .entete button, .poser, .repas-nom, .valider-repas, .annuler-repas {
      min-height: 48px; padding: 0 12px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--divider-color); font-size: 1rem;
      background: var(--card-background-color); color: var(--primary-text-color);
    }
    .grille { display: flex; flex-direction: column; gap: 8px; }
    .ligne-jours, .ligne-creneau { display: flex; gap: 8px; align-items: stretch; }
    .creneau, .coin { flex: 0 0 7em; display: flex; align-items: center;
                      font-weight: 600; }
    .jour { flex: 1; text-align: center; font-weight: 600; }
    .case {
      flex: 1; display: flex; flex-direction: column; gap: 6px; padding: 6px;
      border: 1px dashed var(--divider-color); border-radius: 8px;
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
  `,e([de({attribute:!1})],mt.prototype,"connexion",void 0),e([de({attribute:!1})],mt.prototype,"file",void 0),e([de({type:Boolean})],mt.prototype,"large",void 0),e([de({type:String})],mt.prototype,"debut",void 0),e([he()],mt.prototype,"repas",void 0),e([he()],mt.prototype,"manquants",void 0),e([he()],mt.prototype,"armeAnnulation",void 0),e([he()],mt.prototype,"message",void 0),mt=e([ce("home-stock-planning")],mt);const gt={install:"posée",charge:"rechargée",replacement:"changée",removal:"retirée"};function ft(e){return e.orphaned?"entité introuvable":null===e.last_percent?"jamais relevée":"unavailable"===e.state||"unknown"===e.state?`${Math.trunc(e.last_percent)} % — muette depuis le dernier relevé`:`${Math.trunc(e.last_percent)} %`}function bt(e){if(!e.spare_label)return null;const t="built_in"!==e.kind,i=e.spare_in_stock??0,r=i>0?`${Number.isInteger(i)?i:i.toFixed(1)} en stock`:(t?"aucune":"aucun")+" en stock";return`${e.cell_count}× ${e.spare_label}, ${r}`}let vt=class extends ae{constructor(){super(...arguments),this.piles=[],this.aDeclarer=[],this.selection=null,this.evenements=[],this.armee=null,this.refus=null,this.ignoree=null,this.motif="",this.erreurMotif=null}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(!this.connexion)return;const[e,t]=await Promise.all([this.connexion.appeler("home_stock/batteries/list"),this.connexion.appeler("home_stock/batteries/discover")]);this.piles=[...e.batteries].sort((e,t)=>(e.last_percent??Number.POSITIVE_INFINITY)-(t.last_percent??Number.POSITIVE_INFINITY)||e.label.localeCompare(t.label)),this.aDeclarer=t.sensors}async ecrire(e,t){if(!this.file)return;const i=this.file.ajouter(e,t);return this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0})),this.file.rejouer().then(()=>{this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}),i.reponse}async ouvrir(e){if(this.selection=e.id,this.armee=null,this.refus=null,this.evenements=[],!this.connexion)return;const t=await this.connexion.appeler("home_stock/battery/events",{battery_id:e.id});this.evenements=t.events}async surEvenement(e){const t="built_in"===e.kind||"rechargeable_cell"===e.kind?"charge":"replacement",i=`${e.id}:${t}`;if(this.armee!==i)return void(this.armee=i);this.armee=null;const r=await this.ecrire("home_stock/battery/event",{battery_id:e.id,kind:t});this.refus=r?.spare_refused??null,await this.charger()}async suivre(e){await this.ecrire("home_stock/battery/declare",{label:e.device_name||e.entity_id,kind:"primary",entity_registry_id:e.entity_registry_id,device_id:e.device_id,tracked:!0}),await this.charger()}async confirmerIgnorer(){const e=this.ignoree;e&&(this.motif.trim()?(this.erreurMotif=null,await this.ecrire("home_stock/battery/declare",{label:e.device_name||e.entity_id,kind:"primary",entity_registry_id:e.entity_registry_id,device_id:e.device_id,tracked:!1,exclusion_reason:this.motif.trim()}),this.ignoree=null,this.motif="",await this.charger()):this.erreurMotif="Un motif est nécessaire pour ignorer une pile.")}rendreADeclarer(){return 0===this.aDeclarer.length?H:B`
      <section class="section">
        <h2>${this.aDeclarer.length} pile(s) à déclarer</h2>
        ${this.aDeclarer.map(e=>B`
          <div class="capteur">
            <span class="libelle">${e.device_name??e.entity_id}</span>
            <span class="detail">${e.entity_id}${e.model?` — ${e.model}`:""}</span>
            <span class="detail">${null!==e.state?`${e.state} %`:"sans relevé"}</span>
          </div>
          <button class="action suivre" @click=${()=>this.suivre(e)}>Suivre</button>
          <button class="action ignorer" @click=${()=>{this.ignoree=e,this.erreurMotif=null}}>Ignorer</button>
        `)}
        ${this.ignoree?B`
          <label class="detail" for="motif">Motif — pourquoi cette pile n’est pas suivie</label>
          <input id="motif" class="motif" .value=${this.motif}
            @input=${e=>{this.motif=e.target.value}}>
          ${this.erreurMotif?B`<p class="erreur">${this.erreurMotif}</p>`:H}
          <button class="action confirmer-ignorer" @click=${()=>this.confirmerIgnorer()}>
            Confirmer et ignorer
          </button>
        `:H}
      </section>
    `}rendreFiche(e){const t="built_in"===e.kind||"rechargeable_cell"===e.kind?"charge":"replacement",i=this.armee===`${e.id}:${t}`,r="charge"===t?"de la recharger":"de la changer";return B`
      <section class="section">
        <h2>${e.label}</h2>
        <span class="detail">${e.verb} — ${ft(e)}</span>
        ${bt(e)?B`<span class="detail">${bt(e)}</span>`:H}
        <span class="detail">Seuils : ${e.low_percent} % / ${e.keep_percent} %</span>
        ${e.entity_id?B`<span class="detail">${e.entity_id}</span>`:H}
        <button class="action evenement" @click=${()=>this.surEvenement(e)}>
          ${i?`Confirmer : je viens ${r}`:`Je viens ${r}`}
        </button>
        ${this.refus?B`<p class="refus">${this.refus}</p>`:H}
        <h2>Historique</h2>
        ${0===this.evenements.length?B`<span class="detail">Aucun événement enregistré.</span>`:this.evenements.map(e=>B`
              <span class="evenement-passe">
                ${function(e){const t=new Date(e);if(Number.isNaN(t.getTime()))return e;const i=e=>String(e).padStart(2,"0");return`${i(t.getDate())}/${i(t.getMonth()+1)}/${t.getFullYear()}`}(e.occurred_at)} — ${gt[e.kind]??e.kind}
              </span>`)}
        <button class="action" @click=${()=>{this.selection=null,this.refus=null}}>
          Retour à la liste
        </button>
      </section>
    `}render(){const e=this.piles.find(e=>e.id===this.selection)??null;return e?this.rendreFiche(e):B`
      ${this.rendreADeclarer()}
      <section class="section">
        <h2>${this.piles.length} pile(s) suivie(s)</h2>
        ${this.piles.map(e=>B`
          <button class="pile" @click=${()=>this.ouvrir(e)}>
            <span class="libelle">${e.label}</span>
            <span class="verbe">${e.verb}</span>
            <span class="detail">${ft(e)}</span>
            ${bt(e)?B`<span class="detail">${bt(e)}</span>`:H}
          </button>
        `)}
      </section>
    `}};vt.styles=o`
    :host { display: block; padding: 12px; color: var(--primary-text-color); box-sizing: border-box; }
    * { box-sizing: border-box; max-width: 100%; }
    /* Un entity_id est long et sans espace (sensor.browser_mod_606bfd06_
       browser_battery) : sans coupure, il pousse la page au-delà des 412 px
       de la dalle du téléphone, et le vérificateur de rendu le refuse — à
       juste titre. Pas de backtick dans ce commentaire : il est DANS un
       littéral de gabarit, et il le terminerait. */
    .libelle, .detail, .verbe, .lien { overflow-wrap: anywhere; }
    h2 { font-size: 1rem; margin: 12px 0 8px; }
    .pile, .capteur {
      display: block; width: 100%; min-height: 62px; text-align: left;
      margin-bottom: 8px; padding: 10px 12px; border: none; border-radius: 8px;
      background: var(--secondary-background-color); color: var(--primary-text-color);
      font-size: 0.95rem;
    }
    .libelle { display: block; font-weight: 600; }
    .detail { display: block; font-size: 0.85rem; }
    .verbe { display: block; font-size: 0.85rem; }
    button.action {
      min-height: 62px; width: 100%; border-radius: 8px; border: none;
      margin-bottom: 8px; font-size: 0.95rem;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    button.ignorer { background: var(--secondary-background-color); color: var(--primary-text-color); }
    .motif { width: 100%; min-height: 62px; font-size: 1rem; box-sizing: border-box; }
    .refus, .erreur { margin: 8px 0; font-size: 0.9rem; }
    .evenement-passe { display: block; font-size: 0.85rem; margin-bottom: 4px; }
  `,e([de({attribute:!1})],vt.prototype,"connexion",void 0),e([de({attribute:!1})],vt.prototype,"file",void 0),e([he()],vt.prototype,"piles",void 0),e([he()],vt.prototype,"aDeclarer",void 0),e([he()],vt.prototype,"selection",void 0),e([he()],vt.prototype,"evenements",void 0),e([he()],vt.prototype,"armee",void 0),e([he()],vt.prototype,"refus",void 0),e([he()],vt.prototype,"ignoree",void 0),e([he()],vt.prototype,"motif",void 0),e([he()],vt.prototype,"erreurMotif",void 0),vt=e([ce("home-stock-piles")],vt);const xt="Sans emplacement";function yt(e){const[t,i,r]=e.split("-");return`${r}/${i}/${t}`}function $t(e){return e.warranty_ends_on&&null!==e.days_left?e.days_left<0?`garantie terminée depuis le ${yt(e.warranty_ends_on)}`:`garantie jusqu’au ${yt(e.warranty_ends_on)} — ${e.days_left} jours`:"garantie non renseignée"}let _t=class extends ae{constructor(){super(...arguments),this.equipements=[],this.fiche=null,this.armee=null}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(!this.connexion)return;const e=await this.connexion.appeler("home_stock/equipment/list");this.equipements=e.equipment}async ouvrir(e){if(!this.connexion)return;this.armee=null;const t=await this.connexion.appeler("home_stock/equipment/get",{equipment_id:e.id});this.fiche=t.equipment}async delier(e){this.armee===e.id?(this.armee=null,this.file&&(this.file.ajouter("home_stock/equipment/consumable/unlink",{consumable_id:e.id}),this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0})),await this.file.rejouer(),this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0})),this.fiche&&await this.ouvrir(this.fiche))):this.armee=e.id}groupes(){const e=new Map;for(const t of this.equipements){const i=t.location_name??xt;e.set(i,[...e.get(i)??[],t])}return[...e.entries()].sort(([e],[t])=>e===xt?1:t===xt?-1:e.localeCompare(t))}rendreFiche(e){return B`
      <section class="section">
        <h2>${e.name}</h2>
        <span class="detail">${e.location_name??xt}</span>
        ${e.brand||e.model?B`
          <span class="detail">${[e.brand,e.model].filter(Boolean).join(" ")}</span>`:H}
        ${e.serial?B`<span class="detail">N° de série : ${e.serial}</span>`:H}
        ${e.purchased_on?B`<span class="detail">Acheté le ${yt(e.purchased_on)}</span>`:B`<span class="detail">Date d’achat non renseignée</span>`}
        <span class="detail">${$t(e)}</span>
        ${e.manual_media_id||e.manual_url?B`
          <span class="detail lien">
            Notice : ${e.manual_url??e.manual_media_id}
            ${e.manual_introuvable?" — fichier introuvable":""}
          </span>`:B`<span class="detail">Notice non renseignée</span>`}

        <h2>Consommables</h2>
        ${0===e.consumables.length?B`<span class="detail">Aucun consommable rattaché.</span>`:e.consumables.map(e=>B`
              <div class="equipement">
                <span class="libelle">${e.product_name}</span>
                <span class="detail">
                  ${e.label??e.role} — ${function(e){const t=e.in_stock??0;return t<=0?"aucun en stock":`${Number.isInteger(t)?t:t.toFixed(1)} en stock`}(e)}
                </span>
                ${null!==e.low_value?B`
                  <span class="detail">
                    Seuils : ${e.low_value} / ${e.keep_value}
                    ${"percent"===e.unit?"%":e.unit??""}
                  </span>`:H}
              </div>
              <button class="action delier" @click=${()=>this.delier(e)}>
                ${this.armee===e.id?"Confirmer : délier ce consommable":"Délier ce consommable"}
              </button>
            `)}

        <h2>Piles</h2>
        ${0===e.batteries.length?B`<span class="detail">Aucune pile rattachée.</span>`:e.batteries.map(e=>B`
              <span class="detail">
                ${e.label} — ${e.verb}${null!==e.last_percent?` — ${Math.trunc(e.last_percent)} %`:" — jamais relevée"}
              </span>`)}

        <button class="action" @click=${()=>{this.fiche=null,this.armee=null}}>
          Retour à la liste
        </button>
      </section>
    `}render(){return this.fiche?this.rendreFiche(this.fiche):B`
      ${this.groupes().map(([e,t])=>B`
        <section class="section">
          <h2 class="emplacement">${e}</h2>
          ${t.map(e=>B`
            <button class="equipement" @click=${()=>this.ouvrir(e)}>
              <span class="libelle">${e.name}</span>
              <span class="detail">${$t(e)}</span>
              ${e.consumable_count?B`<span class="detail">${e.consumable_count} consommable(s)</span>`:H}
            </button>
          `)}
        </section>
      `)}
    `}};_t.styles=o`
    :host { display: block; padding: 12px; color: var(--primary-text-color); box-sizing: border-box; }
    * { box-sizing: border-box; max-width: 100%; }
    /* Un entity_id est long et sans espace (sensor.browser_mod_606bfd06_
       browser_battery) : sans coupure, il pousse la page au-delà des 412 px
       de la dalle du téléphone, et le vérificateur de rendu le refuse — à
       juste titre. Pas de backtick dans ce commentaire : il est DANS un
       littéral de gabarit, et il le terminerait. */
    .libelle, .detail, .verbe, .lien { overflow-wrap: anywhere; }
    h2 { font-size: 1rem; margin: 12px 0 8px; }
    .equipement {
      display: block; width: 100%; min-height: 62px; text-align: left;
      margin-bottom: 8px; padding: 10px 12px; border: none; border-radius: 8px;
      background: var(--secondary-background-color); color: var(--primary-text-color);
      font-size: 0.95rem;
    }
    .libelle { display: block; font-weight: 600; }
    .detail { display: block; font-size: 0.85rem; }
    button.action {
      min-height: 62px; width: 100%; border-radius: 8px; border: none;
      margin-bottom: 8px; font-size: 0.95rem;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    button.delier { background: var(--secondary-background-color); color: var(--primary-text-color); }
    .lien { word-break: break-all; }
  `,e([de({attribute:!1})],_t.prototype,"connexion",void 0),e([de({attribute:!1})],_t.prototype,"file",void 0),e([he()],_t.prototype,"equipements",void 0),e([he()],_t.prototype,"fiche",void 0),e([he()],_t.prototype,"armee",void 0),_t=e([ce("home-stock-equipements")],_t);let kt=class extends ae{constructor(){super(...arguments),this.donnees=null,this.enAttente=0,this.cocheesLocalement=new Set,this.decocheesLocalement=new Set,this.retireesLocalement=new Set,this.saisie=""}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){this.connexion&&(this.donnees=await this.connexion.appeler("home_stock/list/items"),this.cocheesLocalement=new Set,this.decocheesLocalement=new Set,this.retireesLocalement=new Set)}ecrire(e,t){this.file&&(this.file.ajouter(e,t),this.avertirFile(),this.file.rejouer().then(()=>{this.avertirFile(),this.charger()}))}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}estCochee(e){return!this.decocheesLocalement.has(e.id)&&(this.cocheesLocalement.has(e.id)||null!==e.checked_at)}cocher(e){this.cocheesLocalement=new Set(this.cocheesLocalement).add(e.id);const t=new Set(this.decocheesLocalement);t.delete(e.id),this.decocheesLocalement=t,this.ecrire("home_stock/list/check",{item_id:e.id})}decocher(e){this.decocheesLocalement=new Set(this.decocheesLocalement).add(e.id);const t=new Set(this.cocheesLocalement);t.delete(e.id),this.cocheesLocalement=t,this.ecrire("home_stock/list/uncheck",{item_id:e.id})}retirer(e){this.retireesLocalement=new Set(this.retireesLocalement).add(e.id),this.ecrire("home_stock/list/remove",{item_id:e.id})}ajouter(){const e=this.saisie.trim();e&&(this.ecrire("home_stock/list/add",{free_text:e}),this.saisie="")}origines(e){return e.claims.map(e=>e.detail).filter(Boolean).join(" · ")}rendreLigne(e,t){const i=e.product_name??e.free_text??"",r=this.origines(e);return B`
      <article class="ligne ${t?"ligne-cochee":""}">
        <button class=${t?"decocher":"cocher"}
          aria-label=${t?`Décocher ${i}`:`Cocher ${i}`}
          @click=${()=>t?this.decocher(e):this.cocher(e)}>
          ${t?"☑":"☐"}
        </button>
        <div class="infos">
          <p class="nom">${i}</p>
          <p class="quantite">${function(e){if(null===e.quantity)return"ce qu’il faut";const t=e.base_unit&&"piece"!==e.base_unit?` ${e.base_unit}`:"";return`${e.quantity}${t}`}(e)}</p>
          ${r?B`<p class="origines">${r}</p>`:H}
        </div>
        <button class="retirer" aria-label=${`Retirer ${i} de la liste`}
          @click=${()=>this.retirer(e)}>×</button>
      </article>
    `}render(){const e=this.donnees;if(!e)return B`<p class="vide">Liste indisponible.</p>`;const t=e.items.filter(e=>!this.retireesLocalement.has(e.id)),i=t.filter(e=>!this.estCochee(e)),r=t.filter(e=>this.estCochee(e)),s=e.estimate;return B`
      <section class="bandeau">
        <p class="magasin">${e.store_name??"Ordre par défaut"}</p>
        <p class="compte">${`${i.length} ligne${i.length>1?"s":""} — ≈ ${n=s.amount,`${n.toFixed(2).replace(".",",")} €`}`}</p>
        <p class="confiance">${`estimation sur ${s.priced} ligne${s.priced>1?"s":""} sur ${s.total}`}</p>
      </section>

      ${this.enAttente>0?B`
        <p class="en-attente">
          ${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau
        </p>
      `:H}

      <section class="ajout">
        <input class="champ-ajout" .value=${this.saisie} placeholder="Ajouter une ligne"
          aria-label="Ajouter une ligne"
          @input=${e=>{this.saisie=e.target.value}} />
        <button class="ajouter" @click=${this.ajouter}>Ajouter</button>
      </section>

      ${0===i.length?B`
        <p class="vide">Rien à acheter pour l’instant.</p>
      `:H}

      ${function(e){const t=[];for(const i of e){const e=i.aisle_name??"Sans rayon",r=t[t.length-1];r&&r.rayon===e?r.lignes.push(i):t.push({rayon:e,lignes:[i]})}return t}(i).map(e=>B`
        <section class="rayon">
          <h3 class="rayon-nom">${e.rayon}</h3>
          ${e.lignes.map(e=>this.rendreLigne(e,!1))}
        </section>
      `)}

      ${r.length>0?B`
        <section class="cochees">
          <h3 class="rayon-nom">Dans le chariot (${r.length})</h3>
          ${r.map(e=>this.rendreLigne(e,!0))}
        </section>
      `:H}
    `;var n}};kt.styles=o`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .bandeau {
      display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px;
      justify-content: space-between; margin-bottom: 8px;
    }
    .magasin { font-weight: 600; margin: 0; }
    .compte { font-size: 1.2rem; font-weight: 700; margin: 0; }
    .confiance { font-size: 0.8rem; color: var(--secondary-text-color); margin: 0; flex-basis: 100%; }
    .en-attente { text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 4px 0 8px; }
    .ajout { display: flex; gap: 8px; margin-bottom: 8px; }
    .champ-ajout { flex: 1; min-height: 48px; box-sizing: border-box; font-size: 1rem; padding: 4px 8px; }
    .ajouter {
      min-height: 48px; min-width: 88px; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .vide { color: var(--secondary-text-color); text-align: center; }
    .rayon-nom {
      margin: 16px 0 4px; font-size: 0.9rem; text-transform: uppercase;
      color: var(--secondary-text-color); letter-spacing: 0.04em;
    }
    .ligne {
      display: flex; align-items: center; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .ligne-cochee .nom { text-decoration: line-through; color: var(--secondary-text-color); }
    .cocher, .decocher {
      min-width: 48px; min-height: 48px; border-radius: 8px; border: none; font-size: 1.3rem;
      background: var(--secondary-background-color); color: var(--primary-text-color); flex-shrink: 0;
    }
    .infos { flex: 1; min-width: 0; }
    .nom { margin: 0; }
    .quantite { margin: 2px 0 0; font-size: 0.9rem; color: var(--secondary-text-color); }
    .origines { margin: 2px 0 0; font-size: 0.8rem; color: var(--secondary-text-color); }
    .retirer {
      min-width: 48px; min-height: 48px; border-radius: 8px; border: none; font-size: 1.2rem;
      background: var(--secondary-background-color); color: var(--primary-text-color); flex-shrink: 0;
    }
  `,e([de({attribute:!1})],kt.prototype,"donnees",void 0),e([de({attribute:!1})],kt.prototype,"connexion",void 0),e([de({attribute:!1})],kt.prototype,"file",void 0),e([de({attribute:!1})],kt.prototype,"enAttente",void 0),e([he()],kt.prototype,"cocheesLocalement",void 0),e([he()],kt.prototype,"decocheesLocalement",void 0),e([he()],kt.prototype,"retireesLocalement",void 0),e([he()],kt.prototype,"saisie",void 0),kt=e([ce("home-stock-liste")],kt);const wt={pending:"Lecture en cours…",read:"Ticket lu",failed:"Lecture impossible",applied:"Prix appliqués",discarded:"Ticket abandonné"};function At(e){return`${e.toFixed(2).replace(".",",")} €`}let Ct=class extends ae{constructor(){super(...arguments),this.ticket=null,this.enAttente=0,this.agentConfigure=!0,this.erreur=null,this.applicationArmee=!1}ecrire(e,t){this.file&&(this.file.ajouter(e,t),this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()))}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}async surPhoto(e){const t=e.target,i=t.files?.[0],r=this.televerser??(e=>this.connexion.televerserMedia(e,"media-source://media_source/local/home_stock/receipts"));if(!i||!this.televerser&&!this.connexion)return;let s;this.erreur=null;try{s=await r(i)}catch(e){return void(this.erreur=function(e){const t=String(e?.message??e);return t.includes("403")||t.includes("401")?"Le téléversement demande un compte administrateur : connectez-vous avec celui du foyer.":t.includes("413")?"Photo refusée : elle dépasse 20 Mo. Reprenez-la en moins grand.":t.includes("415")||t.toLowerCase().includes("image")?"Photo refusée : seules les images sont acceptées.":`Le téléversement a échoué (${t}).`}(e))}this.ecrire("home_stock/receipt/submit",{media_content_id:s})}rapprocher(e,t){this.ecrire("home_stock/receipt/line/match",{line_id:e.id,shopping_line_id:t,state:"confirmed"})}ignorer(e){this.ecrire("home_stock/receipt/line/match",{line_id:e.id,shopping_line_id:null,state:"ignored"})}reessayer(){this.ticket&&this.ecrire("home_stock/receipt/retry",{receipt_id:this.ticket.id})}appliquer(){this.ticket&&(this.ecrire("home_stock/receipt/apply",{receipt_id:this.ticket.id}),this.applicationArmee=!1)}mouvementsACorriger(){const e=this.ticket;if(!e)return 0;const t=new Set(e.lines.filter(e=>null!==e.line_id&&"ignored"!==e.match_state).map(e=>e.line_id));return e.cart_lines.filter(e=>t.has(e.id)).reduce((e,t)=>e+(t.movements??0),0)}chariotPour(e){return null===e.line_id?null:this.ticket?.cart_lines.find(t=>t.id===e.line_id)??null}rendreLigne(e){const t=this.chariotPour(e),i=e.candidates[0]??null;return B`
      <article class="ligne-ticket">
        <div class="cote-ticket">
          <p class="libelle">${e.label}</p>
          <p class="prix">${null===e.total_price?"—":At(e.total_price)}</p>
        </div>
        <div class="cote-chariot">
          ${t?B`
            <p class="rapproche">${t.article_label??t.product_name}</p>
          `:B`
            <p class="orphelin">Aucune ligne de panier — Scanner l’article pour la rattacher</p>
          `}
          ${"ignored"===e.match_state?B`<p class="ignoree">Ignorée</p>`:H}
        </div>
        <div class="actions-ligne">
          ${i?B`
            <button class="rapprocher" @click=${()=>this.rapprocher(e,i.line_id)}>
              ${i.label}
            </button>
          `:H}
          <button class="ignorer" @click=${()=>this.ignorer(e)}>Ignorer</button>
        </div>
      </article>
    `}render(){if(!this.agentConfigure)return B`
        <p class="vide">
          Aucune entité de lecture n’est configurée : choisissez-en une dans les
          réglages du garde-manger pour photographier vos tickets.
        </p>`;const e=this.ticket;return B`
      ${this.enAttente>0?B`
        <p class="en-attente">
          ${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau
        </p>
      `:H}

      ${null===e?B`
        <section class="bloc-principal">
          <label class="prendre-photo">
            Photographier le ticket
            <input class="photo" type="file" accept="image/*" capture="environment"
              @change=${this.surPhoto} />
          </label>
        </section>
      `:this.rendreTicket(e)}

      ${this.erreur?B`<p class="erreur">${this.erreur}</p>`:H}
    `}rendreTicket(e){const t=this.mouvementsACorriger();return B`
      <section class="entete">
        <p class="etat">${wt[e.state]}</p>
        ${null!==e.total?B`
          <p class="total">${At(e.total)}</p>
        `:H}
      </section>

      ${e.error?B`<p class="erreur">${e.error}</p>`:H}

      ${null!==e.total_gap?B`
        <p class="ecart">
          ${`La somme des lignes s’écarte du total de ${At(Math.abs(e.total_gap))}.`}
        </p>
      `:H}

      ${"failed"===e.state?B`
        <button class="reessayer" @click=${this.reessayer}>Réessayer la lecture</button>
      `:H}

      <section class="bloc-principal">
        ${e.lines.map(e=>this.rendreLigne(e))}
      </section>

      ${this.applicationArmee?B`
        <div class="confirmation">
          <p class="avertissement">${0===t?"Aucun mouvement déjà écrit ne sera corrigé.":`${t} mouvement${t>1?"s":""} déjà écrit${t>1?"s":""} seront corrigés.`}</p>
          <button class="confirmer-application" @click=${this.appliquer}>Confirmer</button>
          <button class="annuler-application"
            @click=${()=>{this.applicationArmee=!1}}>Annuler</button>
        </div>
      `:B`
        <button class="appliquer" ?disabled=${"read"!==e.state}
          @click=${()=>{this.applicationArmee=!0}}>
          Appliquer les prix
        </button>
      `}
    `}};Ct.styles=o`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .vide { color: var(--secondary-text-color); text-align: center; }
    .en-attente { text-align: center; color: var(--secondary-text-color); font-size: 0.85rem; margin: 4px 0 8px; }
    .entete { display: flex; justify-content: space-between; align-items: baseline; }
    .etat { font-weight: 600; margin: 0; }
    .total { font-size: 1.3rem; font-weight: 700; margin: 0; }
    .erreur {
      margin: 8px 0; padding: 8px 12px; border-radius: 8px;
      background: var(--error-color, #b3261e); color: #fff; font-size: 0.9rem;
    }
    .ecart { color: var(--warning-color, #8a5300); font-size: 0.9rem; margin: 8px 0; }
    .prendre-photo {
      display: block; min-height: 62px; padding: 16px; border-radius: 12px; text-align: center;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .photo { display: block; margin: 8px auto 0; color: inherit; }
    .ligne-ticket {
      display: flex; flex-wrap: wrap; gap: 8px; padding: 8px 0;
      border-bottom: 1px solid var(--divider-color, #ddd);
    }
    .cote-ticket { flex: 1 1 40%; min-width: 0; }
    .cote-chariot { flex: 1 1 40%; min-width: 0; }
    .libelle { margin: 0; font-family: monospace; }
    .prix { margin: 2px 0 0; font-size: 0.9rem; color: var(--secondary-text-color); }
    .rapproche { margin: 0; }
    .orphelin, .ignoree { margin: 0; font-size: 0.85rem; color: var(--secondary-text-color); }
    .actions-ligne { display: flex; gap: 8px; flex-basis: 100%; }
    .rapprocher, .ignorer, .reessayer {
      min-height: 48px; min-width: 88px; border-radius: 8px; border: none; font-size: 0.9rem;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .appliquer, .confirmer-application, .annuler-application {
      display: block; width: 100%; min-height: 62px; font-size: 1.1rem; border-radius: 12px;
      border: none; margin-top: 12px;
    }
    .appliquer, .confirmer-application {
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .appliquer:disabled { opacity: 0.5; }
    .annuler-application {
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .avertissement { margin: 12px 0 0; font-size: 0.9rem; }
  `,e([de({attribute:!1})],Ct.prototype,"ticket",void 0),e([de({attribute:!1})],Ct.prototype,"connexion",void 0),e([de({attribute:!1})],Ct.prototype,"file",void 0),e([de({attribute:!1})],Ct.prototype,"enAttente",void 0),e([de({attribute:!1})],Ct.prototype,"agentConfigure",void 0),e([de({attribute:!1})],Ct.prototype,"televerser",void 0),e([he()],Ct.prototype,"erreur",void 0),e([he()],Ct.prototype,"applicationArmee",void 0),Ct=e([ce("home-stock-ticket")],Ct);let Et=class extends ae{constructor(){super(...arguments),this.narrow=!1,this.ecran="scanner",this.enAttente=0,this.session=null,this.resultatCourant=null,this.derniereFiche=null,this.enAttenteRangement=[],this.erreurFile=null,this.navigationArmee=null,this.produitAManger=null,this.auRetourDuReseau=()=>{this.file?.rejouer().then(()=>{this.enAttente=this.file.taille()})},this.surCodeLu=async e=>{try{const t=await this.connexion.appeler("home_stock/lookup",{code:e.detail.code});this.resultatCourant=t,this.ecran="fiche"}catch{this.derniereFiche={nom:e.detail.code,marque:null,image:null,statut:"Connexion indisponible — réessayez."}}},this.surArticlePret=e=>{const{articleId:t,quantite:i,prixUnitaire:r,mode:s,offDroppedFields:n}=e.detail;if("panier"===s)return this.file.ajouter("home_stock/session/add_line",{article_id:t,quantity:i,unit_price:r}),this.enAttente=this.file.taille(),this.file.rejouer().then(()=>{this.enAttente=this.file.taille()}),this.derniereFiche=function(e,t,i=[]){return e?{nom:e.off?.label??e.article?.label??e.product?.name??e.code,marque:e.off?.brand??e.article?.brand??null,image:e.off?.image??e.article?.image??null,statut:t,ignores:i}:null}(this.resultatCourant,"Ajouté au panier.",n),this.resultatCourant=null,void(this.ecran="scanner");const o=function(e,t,i,r){return{source:"autonome",id:`autonome-${crypto.randomUUID()}`,article_id:t,quantity:i,unit_price:r,product_name:e?.product?.name??e?.off?.label??e?.article?.label??e?.off?.generic_name??"Article",base_unit:e?.product?.base_unit??"piece",default_location_id:e?.product?.default_location_id??null,default_shelf_life_days:e?.product?.default_shelf_life_days??null,brand:e?.off?.brand??e?.article?.brand??null,image:e?.off?.image??e?.article?.image??null,net_quantity:e?.article?.net_quantity??e?.off?.net_quantity??null}}(this.resultatCourant,t,i,r);this.enAttenteRangement=[...this.enAttenteRangement,o],this.resultatCourant=null,this.ecran="rangement"},this.surSessionChangee=async()=>{await this.actualiserSession(),this.ecran="scanner"},this.surMangerProduit=e=>{this.produitAManger=e.detail.product_id,this.demanderNavigation("consommation")},this.surConsommationEnregistree=()=>{this.produitAManger=null,this.ecran="scanner"},this.surLigneAutonomeRangee=e=>{this.enAttenteRangement=this.enAttenteRangement.filter(t=>t.id!==e.detail.id)},this.surRangementTermine=()=>{this.navigationArmee=null,this.ecran="scanner"},this.surFileChangee=()=>{this.enAttente=this.file.taille()},this.large="undefined"!=typeof window&&window.innerWidth>=1e3,this.surRedimensionnement=()=>{this.large=window.innerWidth>=1e3},this.ticketOuvert=null,this.agentTicketConfigure=!0,this.surAllerListe=()=>{this.demanderNavigation("liste")},this.surTicketOuvert=e=>{this.ticketOuvert=e.detail.ticket,this.agentTicketConfigure=e.detail.agent_configure??!0,this.demanderNavigation("ticket")},this.recetteOuverte=null,this.repasDeLaRecette=null,this.repasAValider=null,this.surRecetteOuverte=e=>{this.recetteOuverte=e.detail.recipe_id,this.repasDeLaRecette=e.detail.meal_id??null,this.demanderNavigation("recette")},this.surValiderRepas=e=>{this.repasAValider=e.detail.meal_id,this.demanderNavigation("validation")},this.surRepasValide=()=>{this.repasAValider=null,this.demanderNavigation("planning")}}connectedCallback(){super.connectedCallback(),window.addEventListener("resize",this.surRedimensionnement),this.addEventListener("recette-ouverte",this.surRecetteOuverte),this.addEventListener("valider-repas",this.surValiderRepas),this.addEventListener("repas-valide",this.surRepasValide),this.connexion=new me(this.hass),this.file=new xe(window.localStorage,(e,t)=>this.connexion.appeler(e,t),(e,t)=>{this.erreurFile=t}),this.enAttente=this.file.taille(),this.file.rejouer().then(()=>{this.enAttente=this.file.taille()}),this.actualiserSession(),this.connexion.abonner(()=>{this.actualiserSession(),this.requestUpdate()}).then(e=>{this.isConnected?this.desabonner=e:e()}),window.addEventListener("online",this.auRetourDuReseau),this.addEventListener("ticket-ouvert",this.surTicketOuvert),this.addEventListener("aller-liste",this.surAllerListe),this.addEventListener("manger-produit",this.surMangerProduit),this.addEventListener("consommation-enregistree",this.surConsommationEnregistree)}disconnectedCallback(){super.disconnectedCallback(),this.desabonner?.(),this.desabonner=void 0,window.removeEventListener("online",this.auRetourDuReseau),window.removeEventListener("resize",this.surRedimensionnement),this.removeEventListener("recette-ouverte",this.surRecetteOuverte),this.removeEventListener("valider-repas",this.surValiderRepas),this.removeEventListener("repas-valide",this.surRepasValide),this.removeEventListener("manger-produit",this.surMangerProduit),this.removeEventListener("consommation-enregistree",this.surConsommationEnregistree)}async actualiserSession(){try{this.session=await this.connexion.appeler("home_stock/session/current")}catch{}}get lignesSessionARanger(){return this.session?.session&&"to_store"===this.session.session.state?this.session.lines.filter(e=>null===e.stored_at).map(e=>({...e,source:"session"})):[]}get lignesARanger(){return[...this.lignesSessionARanger,...this.enAttenteRangement]}demanderNavigation(e){"rangement"===this.ecran&&"rangement"!==e&&this.enAttenteRangement.length>0?this.navigationArmee=e:this.ecran=e}confirmerNavigation(){const e=this.navigationArmee;this.navigationArmee=null,e&&(this.ecran=e)}annulerNavigation(){this.navigationArmee=null}rendreNavigation(){if("fiche"===this.ecran)return H;if(this.navigationArmee)return B`
        <div class="confirmation-quitter-rangement">
          <p>
            Des articles rapportés seuls n’ont pas encore été rangés : ils seront perdus si vous quittez
            maintenant.
          </p>
          <button class="confirmer-quitter" @click=${this.confirmerNavigation}>Quitter quand même</button>
          <button class="annuler-quitter" @click=${this.annulerNavigation}>Rester ici</button>
        </div>
      `;const e="shopping"===this.session?.session?.state,t=this.lignesARanger;return B`
      <nav class="navigation">
        ${"scanner"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("scanner")}>Scanner</button>
        `:H}
        ${e&&"panier"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("panier")}>
            Panier${this.session.totals.lines?` (${this.session.totals.lines})`:""}
          </button>
        `:H}
        ${t.length>0&&"rangement"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("rangement")}>
            Ranger (${t.length})
          </button>
        `:H}
        ${"session"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("session")}>
            Courses
          </button>
        `:H}
        ${"catalogue"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("catalogue")}>Catalogue</button>
        `:H}
        ${"journal"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("journal")}>Journal</button>
        `:H}
        ${"piles"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("piles")}>Piles</button>
        `:H}
        ${"equipements"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("equipements")}>
            Équipements
          </button>
        `:H}
        ${"liste"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("liste")}>Liste</button>
        `:H}
        ${"reglages"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("recettes")}>Recettes</button>
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("planning")}>Planning</button>
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("reglages")}>Réglages</button>
        `:H}
      </nav>
    `}rendreErreurFile(){return this.erreurFile?B`
      <p class="erreur-file">
        ${this.erreurFile}
        <button class="fermer-erreur-file" @click=${()=>{this.erreurFile=null}}>OK</button>
      </p>
    `:H}rendreEcran(){return"fiche"===this.ecran&&this.resultatCourant?B`
        <home-stock-fiche .resultat=${this.resultatCourant}
          .mode=${"shopping"===this.session?.session?.state?"panier":"rangement"}
          .connexion=${this.connexion} .file=${this.file} @article-pret=${this.surArticlePret}>
        </home-stock-fiche>`:"panier"===this.ecran&&this.session?B`
        <home-stock-panier .donnees=${this.session} .connexion=${this.connexion}
          .file=${this.file} .enAttente=${this.enAttente} @file-changee=${this.surFileChangee}>
        </home-stock-panier>`:"rangement"===this.ecran?B`
        <home-stock-rangement .lignes=${this.lignesARanger} .connexion=${this.connexion} .file=${this.file}
          .enAttente=${this.enAttente}
          @ligne-autonome-rangee=${this.surLigneAutonomeRangee} @termine=${this.surRangementTermine}
          @file-changee=${this.surFileChangee}>
        </home-stock-rangement>`:"session"===this.ecran?B`
        <home-stock-session .donnees=${this.session} .connexion=${this.connexion}
          .file=${this.file} .enAttente=${this.enAttente}
          @session-changee=${this.surSessionChangee} @file-changee=${this.surFileChangee}
          >
        </home-stock-session>`:"catalogue"===this.ecran?B`
        <home-stock-catalogue .connexion=${this.connexion} .file=${this.file} .enAttente=${this.enAttente}
          @file-changee=${this.surFileChangee}>
        </home-stock-catalogue>`:"reglages"===this.ecran?B`
        <home-stock-reglages .connexion=${this.connexion} .file=${this.file} .enAttente=${this.enAttente}
          @file-changee=${this.surFileChangee}>
        </home-stock-reglages>`:"consommation"===this.ecran?B`
        <home-stock-consommation .connexion=${this.connexion} .file=${this.file}
          .productId=${this.produitAManger}>
        </home-stock-consommation>`:"journal"===this.ecran?B`
        <home-stock-journal .connexion=${this.connexion} .file=${this.file}
          @file-changee=${this.surFileChangee}>
        </home-stock-journal>`:"recettes"===this.ecran?B`
        <home-stock-recettes .connexion=${this.connexion} .file=${this.file}
          .enAttente=${this.enAttente} @file-changee=${this.surFileChangee}>
        </home-stock-recettes>`:"recette"===this.ecran&&null!==this.recetteOuverte?B`
        <home-stock-recette .connexion=${this.connexion} .file=${this.file}
          .recipeId=${this.recetteOuverte} .mealId=${this.repasDeLaRecette}
          @recette-fermee=${()=>this.demanderNavigation("recettes")}>
        </home-stock-recette>`:"validation"===this.ecran&&null!==this.repasAValider?B`
        <home-stock-validation .connexion=${this.connexion} .file=${this.file}
          .mealId=${this.repasAValider} @file-changee=${this.surFileChangee}>
        </home-stock-validation>`:"planning"===this.ecran?B`
        <home-stock-planning .connexion=${this.connexion} .file=${this.file}
          .large=${this.large} @file-changee=${this.surFileChangee}>
        </home-stock-planning>`:"piles"===this.ecran?B`
        <home-stock-piles .connexion=${this.connexion} .file=${this.file}
          @file-changee=${this.surFileChangee}>
        </home-stock-piles>`:"equipements"===this.ecran?B`
        <home-stock-equipements .connexion=${this.connexion} .file=${this.file}
          @file-changee=${this.surFileChangee}>
        </home-stock-equipements>`:"liste"===this.ecran?B`
        <home-stock-liste .connexion=${this.connexion} .file=${this.file}
          .enAttente=${this.enAttente} @file-changee=${this.surFileChangee}>
        </home-stock-liste>`:"ticket"===this.ecran?B`
        <home-stock-ticket .connexion=${this.connexion} .file=${this.file}
          .enAttente=${this.enAttente} .ticket=${this.ticketOuvert}
          .agentConfigure=${this.agentTicketConfigure}
          @file-changee=${this.surFileChangee}>
        </home-stock-ticket>`:B`
      <home-stock-scanner .session=${this.session?.session?{store:this.session.session.store}:null}
        .derniereFiche=${this.derniereFiche} .enAttente=${this.enAttente} @code-lu=${this.surCodeLu}>
      </home-stock-scanner>`}render(){return B`${this.rendreNavigation()}${this.rendreErreurFile()}${this.rendreEcran()}`}};Et.styles=o`
    :host { display: block; height: 100%; background: var(--primary-background-color); }
    /* flex-wrap : jusqu'à six boutons cohabitent ici (Scanner, Panier,
       Ranger, Courses, Catalogue, Réglages). Sur 412 px de large ils ne
       tiennent pas tous sur une ligne, et un dépassement horizontal fait
       échouer le vérificateur de rendu — à juste titre. Ils passent donc à
       la ligne plutôt que de rétrécir sous la cible de 48 px ou de tronquer
       leur libellé. */
    .navigation { display: flex; flex-wrap: wrap; gap: 8px; padding: 8px 12px 0; }
    .nav-bouton {
      flex: 1 1 auto; min-height: 48px; min-width: 88px; border-radius: 8px; border: none; font-size: 0.95rem;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .erreur-file {
      display: flex; align-items: center; justify-content: space-between; gap: 8px;
      margin: 8px 12px 0; padding: 8px 12px; border-radius: 8px;
      background: var(--error-color, #b3261e); color: #fff; font-size: 0.9rem;
    }
    .fermer-erreur-file {
      min-height: 48px; min-width: 48px; border-radius: 8px; border: none;
      background: rgba(255, 255, 255, 0.2); color: #fff; font-weight: 600;
    }
    .confirmation-quitter-rangement {
      display: flex; flex-direction: column; gap: 8px; padding: 12px;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .confirmation-quitter-rangement p { margin: 0; }
    .confirmer-quitter, .annuler-quitter {
      min-height: 48px; width: 100%; border-radius: 8px; border: none; font-size: 0.95rem;
    }
    .confirmer-quitter { background: var(--error-color, #b3261e); color: #fff; }
    .annuler-quitter { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  `,e([de({attribute:!1})],Et.prototype,"hass",void 0),e([de({attribute:!1})],Et.prototype,"narrow",void 0),e([he()],Et.prototype,"ecran",void 0),e([he()],Et.prototype,"enAttente",void 0),e([he()],Et.prototype,"session",void 0),e([he()],Et.prototype,"resultatCourant",void 0),e([he()],Et.prototype,"derniereFiche",void 0),e([he()],Et.prototype,"enAttenteRangement",void 0),e([he()],Et.prototype,"erreurFile",void 0),e([he()],Et.prototype,"navigationArmee",void 0),e([he()],Et.prototype,"produitAManger",void 0),e([he()],Et.prototype,"large",void 0),e([he()],Et.prototype,"ticketOuvert",void 0),e([he()],Et.prototype,"agentTicketConfigure",void 0),e([he()],Et.prototype,"recetteOuverte",void 0),e([he()],Et.prototype,"repasDeLaRecette",void 0),e([he()],Et.prototype,"repasAValider",void 0),Et=e([ce("home-stock-panel")],Et);export{Et as PanneauGardeManger};
