function e(e,t,i,r){var s,n=arguments.length,o=n<3?t:null===r?r=Object.getOwnPropertyDescriptor(t,i):r;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)o=Reflect.decorate(e,t,i,r);else for(var a=e.length-1;a>=0;a--)(s=e[a])&&(o=(n<3?s(o):n>3?s(t,i,o):s(t,i))||o);return n>3&&o&&Object.defineProperty(t,i,o),o}"function"==typeof SuppressedError&&SuppressedError;
/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const t=globalThis,i=t.ShadowRoot&&(void 0===t.ShadyCSS||t.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,r=Symbol(),s=new WeakMap;let n=class{constructor(e,t,i){if(this._$cssResult$=!0,i!==r)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o;const t=this.t;if(i&&void 0===e){const i=void 0!==t&&1===t.length;i&&(e=s.get(t)),void 0===e&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&s.set(t,e))}return e}toString(){return this.cssText}};const o=(e,...t)=>{const i=1===e.length?e[0]:t.reduce((t,i,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if("number"==typeof e)return e;throw Error("Value passed to 'css' function must be a 'css' function result: "+e+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+e[r+1],e[0]);return new n(i,e,r)},a=i?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t="";for(const i of e.cssRules)t+=i.cssText;return(e=>new n("string"==typeof e?e:e+"",void 0,r))(t)})(e):e,{is:l,defineProperty:c,getOwnPropertyDescriptor:u,getOwnPropertyNames:p,getOwnPropertySymbols:d,getPrototypeOf:h}=Object,m=globalThis,g=m.trustedTypes,f=g?g.emptyScript:"",b=m.reactiveElementPolyfillSupport,v=(e,t)=>e,y={toAttribute(e,t){switch(t){case Boolean:e=e?f:null;break;case Object:case Array:e=null==e?e:JSON.stringify(e)}return e},fromAttribute(e,t){let i=e;switch(t){case Boolean:i=null!==e;break;case Number:i=null===e?null:Number(e);break;case Object:case Array:try{i=JSON.parse(e)}catch(e){i=null}}return i}},x=(e,t)=>!l(e,t),$={attribute:!0,type:String,converter:y,reflect:!1,useDefault:!1,hasChanged:x};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */Symbol.metadata??=Symbol("metadata"),m.litPropertyMetadata??=new WeakMap;let _=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=$){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){const i=Symbol(),r=this.getPropertyDescriptor(e,i,t);void 0!==r&&c(this.prototype,e,r)}}static getPropertyDescriptor(e,t,i){const{get:r,set:s}=u(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){const n=r?.call(this);s?.call(this,t),this.requestUpdate(e,n,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??$}static _$Ei(){if(this.hasOwnProperty(v("elementProperties")))return;const e=h(this);e.finalize(),void 0!==e.l&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(v("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(v("properties"))){const e=this.properties,t=[...p(e),...d(e)];for(const i of t)this.createProperty(i,e[i])}const e=this[Symbol.metadata];if(null!==e){const t=litPropertyMetadata.get(e);if(void 0!==t)for(const[e,i]of t)this.elementProperties.set(e,i)}this._$Eh=new Map;for(const[e,t]of this.elementProperties){const i=this._$Eu(e,t);void 0!==i&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){const t=[];if(Array.isArray(e)){const i=new Set(e.flat(1/0).reverse());for(const e of i)t.unshift(a(e))}else void 0!==e&&t.push(a(e));return t}static _$Eu(e,t){const i=t.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof e?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),void 0!==this.renderRoot&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){const e=new Map,t=this.constructor.elementProperties;for(const i of t.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){const e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((e,r)=>{if(i)e.adoptedStyleSheets=r.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(const i of r){const r=document.createElement("style"),s=t.litNonce;void 0!==s&&r.setAttribute("nonce",s),r.textContent=i.cssText,e.appendChild(r)}})(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,i){this._$AK(e,i)}_$ET(e,t){const i=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,i);if(void 0!==r&&!0===i.reflect){const s=(void 0!==i.converter?.toAttribute?i.converter:y).toAttribute(t,i.type);this._$Em=e,null==s?this.removeAttribute(r):this.setAttribute(r,s),this._$Em=null}}_$AK(e,t){const i=this.constructor,r=i._$Eh.get(e);if(void 0!==r&&this._$Em!==r){const e=i.getPropertyOptions(r),s="function"==typeof e.converter?{fromAttribute:e.converter}:void 0!==e.converter?.fromAttribute?e.converter:y;this._$Em=r;const n=s.fromAttribute(t,e.type);this[r]=n??this._$Ej?.get(r)??n,this._$Em=null}}requestUpdate(e,t,i,r=!1,s){if(void 0!==e){const n=this.constructor;if(!1===r&&(s=this[e]),i??=n.getPropertyOptions(e),!((i.hasChanged??x)(s,t)||i.useDefault&&i.reflect&&s===this._$Ej?.get(e)&&!this.hasAttribute(n._$Eu(e,i))))return;this.C(e,t,i)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:i,reflect:r,wrapped:s},n){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,n??t??this[e]),!0!==s||void 0!==n)||(this._$AL.has(e)||(this.hasUpdated||i||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}const e=this.scheduleUpdate();return null!=e&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}const e=this.constructor.elementProperties;if(e.size>0)for(const[t,i]of e){const{wrapped:e}=i,r=this[t];!0!==e||this._$AL.has(t)||void 0===r||this.C(t,void 0,i,r)}}let e=!1;const t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};_.elementStyles=[],_.shadowRootOptions={mode:"open"},_[v("elementProperties")]=new Map,_[v("finalized")]=new Map,b?.({ReactiveElement:_}),(m.reactiveElementVersions??=[]).push("2.1.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const k=globalThis,w=e=>e,A=k.trustedTypes,C=A?A.createPolicy("lit-html",{createHTML:e=>e}):void 0,E="$lit$",S=`lit$${Math.random().toFixed(9).slice(2)}$`,q="?"+S,P=`<${q}>`,z=document,R=()=>z.createComment(""),j=e=>null===e||"object"!=typeof e&&"function"!=typeof e,F=Array.isArray,N="[ \t\n\f\r]",M=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,L=/-->/g,O=/>/g,U=RegExp(`>|${N}(?:([^\\s"'>=/]+)(${N}*=${N}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),T=/'/g,D=/"/g,I=/^(?:script|style|textarea|title)$/i,B=(e=>(t,...i)=>({_$litType$:e,strings:t,values:i}))(1),H=Symbol.for("lit-noChange"),V=Symbol.for("lit-nothing"),J=new WeakMap,Q=z.createTreeWalker(z,129);function W(e,t){if(!F(e)||!e.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==C?C.createHTML(t):t}const Y=(e,t)=>{const i=e.length-1,r=[];let s,n=2===t?"<svg>":3===t?"<math>":"",o=M;for(let t=0;t<i;t++){const i=e[t];let a,l,c=-1,u=0;for(;u<i.length&&(o.lastIndex=u,l=o.exec(i),null!==l);)u=o.lastIndex,o===M?"!--"===l[1]?o=L:void 0!==l[1]?o=O:void 0!==l[2]?(I.test(l[2])&&(s=RegExp("</"+l[2],"g")),o=U):void 0!==l[3]&&(o=U):o===U?">"===l[0]?(o=s??M,c=-1):void 0===l[1]?c=-2:(c=o.lastIndex-l[2].length,a=l[1],o=void 0===l[3]?U:'"'===l[3]?D:T):o===D||o===T?o=U:o===L||o===O?o=M:(o=U,s=void 0);const p=o===U&&e[t+1].startsWith("/>")?" ":"";n+=o===M?i+P:c>=0?(r.push(a),i.slice(0,c)+E+i.slice(c)+S+p):i+S+(-2===c?t:p)}return[W(e,n+(e[i]||"<?>")+(2===t?"</svg>":3===t?"</math>":"")),r]};class G{constructor({strings:e,_$litType$:t},i){let r;this.parts=[];let s=0,n=0;const o=e.length-1,a=this.parts,[l,c]=Y(e,t);if(this.el=G.createElement(l,i),Q.currentNode=this.el.content,2===t||3===t){const e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;null!==(r=Q.nextNode())&&a.length<o;){if(1===r.nodeType){if(r.hasAttributes())for(const e of r.getAttributeNames())if(e.endsWith(E)){const t=c[n++],i=r.getAttribute(e).split(S),o=/([.?@])?(.*)/.exec(t);a.push({type:1,index:s,name:o[2],strings:i,ctor:"."===o[1]?te:"?"===o[1]?ie:"@"===o[1]?re:ee}),r.removeAttribute(e)}else e.startsWith(S)&&(a.push({type:6,index:s}),r.removeAttribute(e));if(I.test(r.tagName)){const e=r.textContent.split(S),t=e.length-1;if(t>0){r.textContent=A?A.emptyScript:"";for(let i=0;i<t;i++)r.append(e[i],R()),Q.nextNode(),a.push({type:2,index:++s});r.append(e[t],R())}}}else if(8===r.nodeType)if(r.data===q)a.push({type:2,index:s});else{let e=-1;for(;-1!==(e=r.data.indexOf(S,e+1));)a.push({type:7,index:s}),e+=S.length-1}s++}}static createElement(e,t){const i=z.createElement("template");return i.innerHTML=e,i}}function K(e,t,i=e,r){if(t===H)return t;let s=void 0!==r?i._$Co?.[r]:i._$Cl;const n=j(t)?void 0:t._$litDirective$;return s?.constructor!==n&&(s?._$AO?.(!1),void 0===n?s=void 0:(s=new n(e),s._$AT(e,i,r)),void 0!==r?(i._$Co??=[])[r]=s:i._$Cl=s),void 0!==s&&(t=K(e,s._$AS(e,t.values),s,r)),t}class Z{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){const{el:{content:t},parts:i}=this._$AD,r=(e?.creationScope??z).importNode(t,!0);Q.currentNode=r;let s=Q.nextNode(),n=0,o=0,a=i[0];for(;void 0!==a;){if(n===a.index){let t;2===a.type?t=new X(s,s.nextSibling,this,e):1===a.type?t=new a.ctor(s,a.name,a.strings,this,e):6===a.type&&(t=new se(s,this,e)),this._$AV.push(t),a=i[++o]}n!==a?.index&&(s=Q.nextNode(),n++)}return Q.currentNode=z,r}p(e){let t=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(e,i,t),t+=i.strings.length-2):i._$AI(e[t])),t++}}class X{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,i,r){this.type=2,this._$AH=V,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=i,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode;const t=this._$AM;return void 0!==t&&11===e?.nodeType&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=K(this,e,t),j(e)?e===V||null==e||""===e?(this._$AH!==V&&this._$AR(),this._$AH=V):e!==this._$AH&&e!==H&&this._(e):void 0!==e._$litType$?this.$(e):void 0!==e.nodeType?this.T(e):(e=>F(e)||"function"==typeof e?.[Symbol.iterator])(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==V&&j(this._$AH)?this._$AA.nextSibling.data=e:this.T(z.createTextNode(e)),this._$AH=e}$(e){const{values:t,_$litType$:i}=e,r="number"==typeof i?this._$AC(e):(void 0===i.el&&(i.el=G.createElement(W(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===r)this._$AH.p(t);else{const e=new Z(r,this),i=e.u(this.options);e.p(t),this.T(i),this._$AH=e}}_$AC(e){let t=J.get(e.strings);return void 0===t&&J.set(e.strings,t=new G(e)),t}k(e){F(this._$AH)||(this._$AH=[],this._$AR());const t=this._$AH;let i,r=0;for(const s of e)r===t.length?t.push(i=new X(this.O(R()),this.O(R()),this,this.options)):i=t[r],i._$AI(s),r++;r<t.length&&(this._$AR(i&&i._$AB.nextSibling,r),t.length=r)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){const t=w(e).nextSibling;w(e).remove(),e=t}}setConnected(e){void 0===this._$AM&&(this._$Cv=e,this._$AP?.(e))}}class ee{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,i,r,s){this.type=1,this._$AH=V,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=s,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=V}_$AI(e,t=this,i,r){const s=this.strings;let n=!1;if(void 0===s)e=K(this,e,t,0),n=!j(e)||e!==this._$AH&&e!==H,n&&(this._$AH=e);else{const r=e;let o,a;for(e=s[0],o=0;o<s.length-1;o++)a=K(this,r[i+o],t,o),a===H&&(a=this._$AH[o]),n||=!j(a)||a!==this._$AH[o],a===V?e=V:e!==V&&(e+=(a??"")+s[o+1]),this._$AH[o]=a}n&&!r&&this.j(e)}j(e){e===V?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}}class te extends ee{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===V?void 0:e}}class ie extends ee{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==V)}}class re extends ee{constructor(e,t,i,r,s){super(e,t,i,r,s),this.type=5}_$AI(e,t=this){if((e=K(this,e,t,0)??V)===H)return;const i=this._$AH,r=e===V&&i!==V||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,s=e!==V&&(i===V||r);r&&this.element.removeEventListener(this.name,this,i),s&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}}class se{constructor(e,t,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){K(this,e)}}const ne=k.litHtmlPolyfillSupport;ne?.(G,X),(k.litHtmlVersions??=[]).push("3.3.3");const oe=globalThis;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */class ae extends _{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){const t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=((e,t,i)=>{const r=i?.renderBefore??t;let s=r._$litPart$;if(void 0===s){const e=i?.renderBefore??null;r._$litPart$=s=new X(t.insertBefore(R(),e),e,void 0,i??{})}return s._$AI(e),s})(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return H}}ae._$litElement$=!0,ae.finalized=!0,oe.litElementHydrateSupport?.({LitElement:ae});const le=oe.litElementPolyfillSupport;le?.({LitElement:ae}),(oe.litElementVersions??=[]).push("4.2.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const ce=e=>(t,i)=>{void 0!==i?i.addInitializer(()=>{customElements.define(e,t)}):customElements.define(e,t)},ue={attribute:!0,type:String,converter:y,reflect:!1,hasChanged:x},pe=(e=ue,t,i)=>{const{kind:r,metadata:s}=i;let n=globalThis.litPropertyMetadata.get(s);if(void 0===n&&globalThis.litPropertyMetadata.set(s,n=new Map),"setter"===r&&((e=Object.create(e)).wrapped=!0),n.set(i.name,e),"accessor"===r){const{name:r}=i;return{set(i){const s=t.get.call(this);t.set.call(this,i),this.requestUpdate(r,s,e,!0,i)},init(t){return void 0!==t&&this.C(r,void 0,e,t),t}}}if("setter"===r){const{name:r}=i;return function(i){const s=this[r];t.call(this,i),this.requestUpdate(r,s,e,!0,i)}}throw Error("Unsupported decorator location: "+r)};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function de(e){return(t,i)=>"object"==typeof i?pe(e,t,i):((e,t,i)=>{const r=t.hasOwnProperty(i);return t.constructor.createProperty(i,e),r?Object.getOwnPropertyDescriptor(t,i):void 0})(e,t,i)}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function he(e){return de({...e,state:!0,attribute:!1})}class me{constructor(e){this.hass=e}appeler(e,t={}){return this.hass.connection.sendMessagePromise({type:e,...t})}abonner(e){return this.hass.connection.subscribeMessage(e,{type:"home_stock/subscribe"})}appelerService(e,t,i={}){return this.hass.callService(e,t,i)}}function ge(e){return!!e&&"object"==typeof e&&"string"==typeof e.code&&"string"==typeof e.message}const fe=new Set(["not_loaded","invalid_field","invalid_value","not_found","already_exists","conversion_refused","shopping_refused","insufficient_stock"]);function be(e){return fe.has(e.code)?e.message:"Une action a été refusée et n’a pas pu être envoyée."}const ve="home_stock.file";class ye{constructor(e,t,i){this.stockage=e,this.envoyer=t,this.surRefus=i,this.actions=[],this.enVol=null;try{this.actions=JSON.parse(this.stockage.getItem(ve)??"[]")}catch{this.actions=[]}}ajouter(e,t){const i={...t};let r;"string"!=typeof i.idempotency_key&&(i.idempotency_key=crypto.randomUUID());const s=new Promise(e=>{r=e});let n;const o=new Promise(e=>{n=e});return this.actions.push({type:e,charge:i,resoudre:r,repondre:n}),this.ecrire(),{cle:i.idempotency_key,sort:s,reponse:o}}taille(){return this.actions.length}async rejouer(){const e=this.enVol,t=(async()=>{e&&await e.catch(()=>{}),await this.boucle()})();this.enVol=t;try{await t}finally{this.enVol===t&&(this.enVol=null)}}async boucle(){for(;this.actions.length;){const e=this.actions[0];let t;try{t=await this.envoyer(e.type,e.charge)}catch(t){if(ge(t)){this.actions.shift(),this.ecrire(),e.resoudre?.("refusee"),e.repondre?.(void 0),this.surRefus?.(e,be(t));continue}for(const e of this.actions)e.resoudre?.("en-attente"),e.repondre?.(void 0),e.resoudre=void 0,e.repondre=void 0;return}this.actions.shift(),this.ecrire(),e.resoudre?.("envoyee"),e.repondre?.(t)}}ecrire(){this.stockage.setItem(ve,JSON.stringify(this.actions.map(({type:e,charge:t})=>({type:e,charge:t}))))}}class xe{constructor(e){this.fenetre=e,this.voie="companion"}disponible(){return Boolean(this.fenetre?.externalApp?.externalBus||this.fenetre?.webkit?.messageHandlers?.externalBus)}lire(){return new Promise(e=>{const t=this.fenetre.externalBus;let i=!1;const r=r=>{i||(i=!0,clearTimeout(s),this.fenetre.externalBus=t,e(r))},s=setTimeout(()=>r(null),6e4);this.fenetre.externalBus=e=>{const t="string"==typeof e?JSON.parse(e):e;return"bar_code/scan_result"===t.command?(this.envoyer({type:"bar_code/close"}),r(String(t.payload.rawValue))):"bar_code/aborted"!==t.command&&"bar_code/close"!==t.command||r(null),!0},this.envoyer({type:"bar_code/scan",payload:{title:"Scanner un article",description:"Visez le code-barres",alternative_option_label:"Saisir le code"}})})}envoyer(e){const t=JSON.stringify(e);this.fenetre.externalApp?.externalBus?this.fenetre.externalApp.externalBus(t):this.fenetre.webkit.messageHandlers.externalBus.postMessage(e)}}const $e=["ean_13","ean_8","upc_a","upc_e","code_128"];class _e{constructor(e){this.fenetre=e,this.voie="navigateur"}disponible(){return Boolean(this.fenetre?.BarcodeDetector&&this.fenetre?.navigator?.mediaDevices)}async lire(){try{const e=new this.fenetre.BarcodeDetector({formats:$e});this.flux=await this.fenetre.navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}});const t=this.fenetre.document.createElement("video");t.srcObject=this.flux,t.setAttribute("playsinline","true"),t.setAttribute("muted","true"),t.style.cssText="position:fixed;inset:0;width:100%;height:100%;object-fit:cover;z-index:2147483647;background:#000;",this.fenetre.document.body.appendChild(t),this.video=t,await t.play();for(let i=0;i<300;i+=1){const i=await e.detect(t);if(i.length)return String(i[0].rawValue);await new Promise(e=>this.fenetre.requestAnimationFrame(e))}return null}finally{this.arreter()}}arreter(){this.flux?.getTracks().forEach(e=>e.stop()),this.flux=void 0,this.video?.remove(),this.video=void 0}}class ke{constructor(){this.voie="clavier"}disponible(){return!0}async lire(){return null}}const we={label:"nom",brand:"marque",net_quantity:"poids net",image:"image",kcal_per_base_unit:"calories",proteins:"protéines",carbohydrates:"glucides",sugars:"sucres",added_sugars:"sucres ajoutés",fat:"matières grasses",saturated_fat:"graisses saturées",fiber:"fibres",salt:"sel",nutriscore:"Nutri-Score",nova:"classification NOVA",ecoscore:"Éco-score",allergens:"allergènes",traces:"traces",additives:"additifs",off_labels:"labels",off_raw:"réponse Open Food Facts"};function Ae(e,t,i){return null==e?"":"piece"===t?e.toFixed(2).replace(".",","):"g"===t||"ml"===t?null===i||i<=0?"":(e*i).toFixed(2).replace(".",","):""}function Ce(e,t,i){const r=Number.parseFloat(e.trim().replace(",","."));return Number.isFinite(r)?"piece"===t?r:"g"===t||"ml"===t?null===i||i<=0?null:r/i:null:null}function Ee(e){return e.known?e.article?.net_quantity??null:e.off?.net_quantity??null}function Se(e){return e&&"object"==typeof e&&"message"in e&&"string"==typeof e.message?e.message:"Une erreur est survenue."}let qe=class extends ae{constructor(){super(...arguments),this.mode="rangement",this.productChoisi=null,this.nomNouveauProduit="",this.uniteNouveauProduit="piece",this.prixSaisi=null,this.poidsPaquet="",this.quantitePaquets=1,this.produitsBaseUnit={},this.rapportConversion=null,this.erreurConversion=null,this.erreurAction=null,this.erreurUnites=null,this.enCours=!1}willUpdate(e){if(e.has("resultat")&&this.resultat){this.productChoisi=this.resultat.preselected_product_id,this.nomNouveauProduit=this.resultat.off?.generic_name??"",this.uniteNouveauProduit=this.resultat.off?.net_unit??"piece";const e=Ee(this.resultat);this.poidsPaquet=null!==e?String(e):"",this.prixSaisi=null,this.quantitePaquets=1,this.rapportConversion=null,this.erreurConversion=null,this.erreurAction=null,this.erreurUnites=null,this.produitsBaseUnit={}}}updated(e){e.has("resultat")&&this.resultat&&!this.resultat.known&&this.resultat.candidates.length&&this.connexion&&this.chargerUnitesProduits()}async chargerUnitesProduits(){this.erreurUnites=null;try{const e=await this.connexion.appeler("home_stock/products/list"),t={};for(const i of e.products)t[i.id]=i.base_unit;this.produitsBaseUnit=t}catch{this.erreurUnites="Impossible de récupérer les informations du produit. Vérifiez la connexion."}}uniteConnue(){return this.resultat.known?this.resultat.product?.base_unit??null:"new"===this.productChoisi?this.uniteNouveauProduit:"number"==typeof this.productChoisi?this.produitsBaseUnit[this.productChoisi]??null:null}get poidsEffectif(){return function(e){const t=Number.parseFloat(e.trim().replace(",","."));return Number.isFinite(t)&&t>0?t:null}(this.poidsPaquet)}get valeurPrix(){if(null!==this.prixSaisi)return this.prixSaisi;const e=this.uniteConnue(),t="piece"===e?null:this.poidsEffectif;return Ae(this.resultat.price?.price_per_base_unit,e,t)}get raisonBlocage(){if(!this.resultat)return null;if(!this.resultat.known){if(!this.connexion)return"Connexion indisponible.";if(null===this.productChoisi)return"Choisissez un produit.";if("new"===this.productChoisi&&!this.nomNouveauProduit.trim())return"Donnez un nom au nouveau produit."}const e=this.uniteConnue();return null===e?this.erreurUnites??"Chargement des informations du produit…":"g"!==e&&"ml"!==e||null!==this.poidsEffectif?null:"Indiquez le poids du paquet pour calculer le prix."}get peutValider(){return!this.enCours&&null===this.raisonBlocage}enregistrerPoidsCorrige(e,t){const i={article_id:e,fields:{net_quantity:t}};this.file?this.file.ajouter("home_stock/article/update",i):this.connexion&&this.connexion.appeler("home_stock/article/update",i).catch(()=>{})}async valider(){if(this.peutValider){this.enCours=!0,this.erreurAction=null;try{const e=this.uniteConnue(),t="piece"===e?null:this.poidsEffectif,i=null===Ee(this.resultat);let r,s=[];if(this.resultat.known)r=this.resultat.article.id,null!==t&&i&&this.enregistrerPoidsCorrige(r,t);else{const e={code:this.resultat.code};this.resultat.off_raw&&(e.off=this.resultat.off_raw),this.resultat.off_source&&(e.off_source=this.resultat.off_source),"new"===this.productChoisi?e.new_product={name:this.nomNouveauProduit.trim(),base_unit:this.uniteNouveauProduit}:e.product_id=this.productChoisi,null!==t&&i&&(e.fields={net_quantity:t});const n=await this.connexion.appeler("home_stock/article/create",e);r=n.article_id,s=n.off_dropped_fields??[]}const n={articleId:r,quantite:"piece"===e?this.quantitePaquets:t*this.quantitePaquets,prixUnitaire:Ce(this.valeurPrix,e,t),mode:this.mode,offDroppedFields:s};this.dispatchEvent(new CustomEvent("article-pret",{detail:n,bubbles:!0,composed:!0}))}catch(e){this.erreurAction=Se(e)}finally{this.enCours=!1}}}mangerProduit(e){this.dispatchEvent(new CustomEvent("manger-produit",{detail:{product_id:e},bubbles:!0,composed:!0}))}async voirEffetConversion(){const e=this.resultat.conversion_offer;if(e&&this.connexion){this.erreurConversion=null;try{this.rapportConversion=await this.connexion.appeler("home_stock/product/convert_unit",{product_id:e.product_id,to_unit:e.to_unit,reference_quantity:e.reference_quantity,dry_run:!0})}catch(e){this.erreurConversion=Se(e)}}}async appliquerConversion(){const e=this.resultat.conversion_offer;if(e&&this.connexion&&this.rapportConversion){this.erreurConversion=null;try{this.rapportConversion=await this.connexion.appeler("home_stock/product/convert_unit",{product_id:e.product_id,to_unit:e.to_unit,reference_quantity:e.reference_quantity,dry_run:!1})}catch(e){this.erreurConversion=Se(e)}}}rendreRattachement(){return this.resultat.known?V:B`
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
          </div>`:V}
        ${this.erreurUnites?B`
          <p class="erreur-unite">${this.erreurUnites}</p>
          <button class="reessayer-unite" @click=${()=>{this.chargerUnitesProduits()}}>
            Réessayer
          </button>`:V}
      </section>
    `}rendreAlerteOff(){const e=this.resultat;return e.known||e.off?V:e.throttled?B`<p class="alerte-off">Open Food Facts limite les requêtes en ce moment — réessayez
        dans un instant plutôt que de créer un doublon.</p>`:e.timed_out?B`<p class="alerte-off">Open Food Facts n'a pas répondu à temps — le produit existe
        peut-être déjà là-bas, réessayez avant de créer un doublon.</p>`:V}rendreConversion(){const e=this.resultat.conversion_offer;return e?B`
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
        ${this.erreurConversion?B`<p class="erreur-conversion">${this.erreurConversion}</p>`:V}
      </section>
    `:V}render(){if(!this.resultat)return V;const e=this.resultat,t=e.off?.label??e.article?.label??e.product?.name??"Article",i=e.off?.brand??e.article?.brand??null,r=e.article?.net_quantity??e.off?.net_quantity??null,s=e.product?.base_unit??e.off?.net_unit??"",n=e.off?.image??e.article?.image??null,o=e.off?.nutriscore??e.article?.nutriscore??null,a=function(e){const t=e.off?.nutrition_per_100?.kcal;if(null!=t)return t;const i=e.article?.kcal_per_base_unit,r=e.product?.base_unit;return null==i||"g"!==r&&"ml"!==r?null:100*i}(e),l=this.uniteConnue(),c="piece"===l?null:this.poidsEffectif,u="g"===l||"ml"===l?Ce(this.valeurPrix,l,c):null,p=null!=u?1e3*u:null,d="ml"===l?"L":"kg";return B`
      <section class="entete">
        ${n?B`<img class="image" src=${n} alt="" />`:V}
        <h2 class="nom">${t}</h2>
        ${i?B`<p class="marque">${i}</p>`:V}
        ${r?B`<p class="poids">${r} ${s}</p>`:V}
        ${o?B`<p class="nutriscore">Nutri-Score ${o.toUpperCase()}</p>`:V}
        ${null!=a?B`<p class="kcal">${Math.round(a)} kcal / 100 g</p>`:V}
      </section>

      ${this.rendreAlerteOff()}
      ${this.rendreRattachement()}

      <section class="prix">
        <p class="prix-provenance">${h=e.price,h&&null!=h.price_per_base_unit&&h.source?"store"===h.source?h.store?`dernier prix ${h.store}`:"dernier prix en magasin":"open_prices"===h.source?"Open Prices":"dernier prix connu":"Aucun prix connu"}</p>
        ${"g"!==l&&"ml"!==l||null!==Ee(e)?V:B`
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
        `:V}
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

      ${this.raisonBlocage?B`<p class="motif-blocage">${this.raisonBlocage}</p>`:V}
      ${this.erreurAction?B`<p class="erreur-action">${this.erreurAction}</p>`:V}

      <button class="action-principale" ?disabled=${!this.peutValider} @click=${this.valider}>
        ${"panier"===this.mode?"Au panier":"Ranger"}
      </button>
      ${null!=e.product?.id?B`
        <button type="button" class="manger" @click=${()=>this.mangerProduit(e.product.id)}>
          Manger
        </button>
      `:V}
    `;var h}};qe.styles=o`
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
  `,e([de({attribute:!1})],qe.prototype,"resultat",void 0),e([de({attribute:!1})],qe.prototype,"mode",void 0),e([de({attribute:!1})],qe.prototype,"connexion",void 0),e([de({attribute:!1})],qe.prototype,"file",void 0),e([he()],qe.prototype,"productChoisi",void 0),e([he()],qe.prototype,"nomNouveauProduit",void 0),e([he()],qe.prototype,"uniteNouveauProduit",void 0),e([he()],qe.prototype,"prixSaisi",void 0),e([he()],qe.prototype,"poidsPaquet",void 0),e([he()],qe.prototype,"quantitePaquets",void 0),e([he()],qe.prototype,"produitsBaseUnit",void 0),e([he()],qe.prototype,"rapportConversion",void 0),e([he()],qe.prototype,"erreurConversion",void 0),e([he()],qe.prototype,"erreurAction",void 0),e([he()],qe.prototype,"erreurUnites",void 0),e([he()],qe.prototype,"enCours",void 0),qe=e([ce("home-stock-fiche")],qe);let Pe=class extends ae{constructor(){super(...arguments),this.fenetre=window,this.derniereFiche=null,this.session=null,this.enAttente=0,this.saisieOuverte=!1,this.codeSaisi="",this.enCours=!1,this.erreur=null}obtenirScanner(){return this.scanner||(this.scanner=function(e){const t=new xe(e);if(t.disponible())return t;const i=new _e(e);return i.disponible()?i:new ke}(this.fenetre??window)),this.scanner}async lancerScan(){const e=this.obtenirScanner();if("clavier"!==e.voie){this.enCours=!0,this.erreur=null;try{const t=await e.lire();t&&this.emettreCode(t)}catch{this.erreur="La caméra n’a pas pu être utilisée. Essayez la saisie manuelle."}finally{this.enCours=!1}}else this.saisieOuverte=!0}emettreCode(e){this.saisieOuverte=!1,this.codeSaisi="",this.dispatchEvent(new CustomEvent("code-lu",{detail:{code:e},bubbles:!0,composed:!0}))}validerSaisie(){const e=this.codeSaisi.trim();e&&this.emettreCode(e)}render(){return B`
      ${this.session?B`
        <p class="session-banniere">
          Session ouverte${this.session.store?` — ${this.session.store}`:""}
        </p>`:V}

      <button class="bouton-scan" ?disabled=${this.enCours} @click=${this.lancerScan}>
        ${this.enCours?"Scan en cours…":"Scanner un article"}
      </button>

      ${this.erreur?B`<p class="erreur">${this.erreur}</p>`:V}

      ${this.derniereFiche?B`
        <section class="derniere-fiche">
          ${this.derniereFiche.image?B`<img src=${this.derniereFiche.image} alt="" />`:V}
          <p class="derniere-fiche-nom">
            ${this.derniereFiche.nom}${this.derniereFiche.marque?` — ${this.derniereFiche.marque}`:""}
          </p>
          <p class="derniere-fiche-statut">${this.derniereFiche.statut}</p>
          ${void 0!==this.derniereFiche.quantite?B`
            <p class="derniere-fiche-quantite">
              Quantité : ${this.derniereFiche.quantite}${null!=this.derniereFiche.prixTotal?` — ${this.derniereFiche.prixTotal.toFixed(2).replace(".",",")} €`:""}
            </p>`:V}
          ${this.derniereFiche.ignores?.length?B`
            <p class="derniere-fiche-ignores">
              Ignoré par Open Food Facts : ${e=this.derniereFiche.ignores,e.map(e=>we[e]??e).join(", ")}
            </p>`:V}
        </section>`:V}

      ${this.enAttente>0?B`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:V}

      <button class="bouton-saisie" @click=${()=>{this.saisieOuverte=!this.saisieOuverte}}>
        Saisir le code
      </button>

      ${this.saisieOuverte?B`
        <div class="saisie-manuelle">
          <input class="champ-code" inputmode="numeric" placeholder="Code-barres" .value=${this.codeSaisi}
            @input=${e=>{this.codeSaisi=e.target.value}}
            @keydown=${e=>{"Enter"===e.key&&this.validerSaisie()}} />
          <button class="valider-saisie" @click=${this.validerSaisie}>Valider</button>
        </div>`:V}
    `;var e}};Pe.styles=o`
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
  `,e([de({attribute:!1})],Pe.prototype,"fenetre",void 0),e([de({attribute:!1})],Pe.prototype,"derniereFiche",void 0),e([de({attribute:!1})],Pe.prototype,"session",void 0),e([de({attribute:!1})],Pe.prototype,"enAttente",void 0),e([he()],Pe.prototype,"saisieOuverte",void 0),e([he()],Pe.prototype,"codeSaisi",void 0),e([he()],Pe.prototype,"enCours",void 0),e([he()],Pe.prototype,"erreur",void 0),Pe=e([ce("home-stock-scanner")],Pe);let ze=class extends ae{constructor(){super(...arguments),this.donnees=null,this.enAttente=0,this.ligneArmee=null,this.prixSaisiParLigne={},this.erreurPrixParLigne={},this.deltaParLigne={},this.quantiteVueParLigne={}}willUpdate(e){if(e.has("donnees")){this.ligneArmee=null;for(const e of this.donnees?.lines??[])if(this.quantiteVueParLigne[e.id]!==e.quantity&&(this.quantiteVueParLigne[e.id]=e.quantity,this.deltaParLigne[e.id])){const{[e.id]:t,...i}=this.deltaParLigne;this.deltaParLigne=i}}}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()),i.sort.then(e=>"envoyee"===e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}quantiteAffichee(e){return e.quantity+(this.deltaParLigne[e.id]??0)}ajusterQuantite(e,t){this.ligneArmee=null;const i=(this.deltaParLigne[e.id]??0)+t,r=e.quantity+i;r<=0||(this.deltaParLigne={...this.deltaParLigne,[e.id]:i},this.ecrire("home_stock/session/update_line",{line_id:e.id,quantity:r}))}saisirPrix(e,t){this.ligneArmee=null,this.prixSaisiParLigne={...this.prixSaisiParLigne,[e.id]:t}}validerPrix(e){this.ligneArmee=null;const t=this.prixSaisiParLigne[e.id];if(void 0===t)return;const i=Ce(t,e.base_unit,e.net_quantity);if(null===i)return void(this.erreurPrixParLigne={...this.erreurPrixParLigne,[e.id]:"Prix non enregistré : poids du paquet inconnu."});if(this.erreurPrixParLigne[e.id]){const{[e.id]:t,...i}=this.erreurPrixParLigne;this.erreurPrixParLigne=i}this.ecrire("home_stock/session/update_line",{line_id:e.id,unit_price:i});const{[e.id]:r,...s}=this.prixSaisiParLigne;this.prixSaisiParLigne=s}supprimer(e){this.ecrire("home_stock/session/remove_line",{line_id:e.id}),this.ligneArmee=null}passerEnCaisse(){this.ligneArmee=null,this.ecrire("home_stock/session/checkout",{})}valeurPrix(e){const t=this.prixSaisiParLigne[e.id];return void 0!==t?t:Ae(e.unit_price,e.base_unit,e.net_quantity)}rendreLigne(e){const t=function(e){return"piece"===e.base_unit?1:e.net_quantity&&e.net_quantity>0?e.net_quantity:1}(e),i=this.quantiteAffichee(e),r=e.article_label??e.product_name;return B`
      <article class="ligne">
        ${e.image?B`<img class="image" src=${e.image} alt="" />`:V}
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
          `:V}
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
    `}render(){const e=this.donnees;if(!e)return B`<p class="vide">Aucune session de courses ouverte.</p>`;const t=function(e){const t=[];for(const i of e){const e=i.aisle_name??"Sans rayon",r=t[t.length-1];r&&r.rayon===e?r.lignes.push(i):t.push({rayon:e,lignes:[i]})}return t}(e.lines),i="shopping"!==e.session.state;return B`
      <section class="entete">
        <p class="magasin">${e.session.store??"Sans enseigne"}</p>
        <p class="total">${r=e.totals.total,`${r.toFixed(2).replace(".",",")} €`}</p>
      </section>

      ${this.enAttente>0?B`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:V}

      ${0===e.lines.length?B`<p class="vide">Le panier est vide.</p>`:V}

      ${t.map(e=>B`
        <section class="rayon">
          <h3 class="rayon-nom">${e.rayon}</h3>
          ${e.lignes.map(e=>this.rendreLigne(e))}
        </section>
      `)}

      <button class="checkout" ?disabled=${0===e.totals.lines||i} @click=${this.passerEnCaisse}>
        ${i?"Déjà en caisse":"Passage en caisse"}
      </button>
    `;var r}};ze.styles=o`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .entete { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
    .magasin { font-weight: 600; margin: 0; }
    .total { font-size: 1.3rem; font-weight: 700; margin: 0; }
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
  `,e([de({attribute:!1})],ze.prototype,"donnees",void 0),e([de({attribute:!1})],ze.prototype,"connexion",void 0),e([de({attribute:!1})],ze.prototype,"file",void 0),e([de({attribute:!1})],ze.prototype,"enAttente",void 0),e([he()],ze.prototype,"ligneArmee",void 0),e([he()],ze.prototype,"prixSaisiParLigne",void 0),e([he()],ze.prototype,"erreurPrixParLigne",void 0),e([he()],ze.prototype,"deltaParLigne",void 0),ze=e([ce("home-stock-panier")],ze);let Re=class extends ae{constructor(){super(...arguments),this.donnees=null,this.enAttente=0,this.magasins=[],this.magasinChoisi=null,this.magasinSaisi="",this.erreurMagasins=null,this.clotureArmee=!1,this.enCours=!1,this.message=null}connectedCallback(){super.connectedCallback(),this.chargerMagasins()}willUpdate(e){e.has("donnees")&&(this.clotureArmee=!1)}async chargerMagasins(){if(this.erreurMagasins=null,this.donnees?.stores?.length&&(this.magasins=this.donnees.stores),this.connexion)try{const e=await this.connexion.appeler("home_stock/stores/list");this.magasins=e.stores}catch{this.erreurMagasins="Impossible de récupérer les magasins connus. Saisissez-en un."}}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()),i.sort.then(e=>"envoyee"===e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}get magasinRetenu(){const e=this.magasinSaisi.trim();return e||this.magasinChoisi}async ouvrir(){if(this.enCours)return;this.enCours=!0,this.message=null;const e=this.magasinRetenu,t=await this.ecrire("home_stock/session/start",e?{store:e}:{});this.enCours=!1,t?this.dispatchEvent(new CustomEvent("session-changee",{detail:{action:"ouverte"},bubbles:!0,composed:!0})):this.message="Envoi en attente de réseau : la session s’ouvrira à la reconnexion."}async clore(){if(!this.clotureArmee||this.enCours)return;this.enCours=!0,this.message=null;const e=await this.ecrire("home_stock/session/close",{});this.enCours=!1,this.clotureArmee=!1,e?this.dispatchEvent(new CustomEvent("session-changee",{detail:{action:"fermee"},bubbles:!0,composed:!0})):this.message="Envoi en attente de réseau : la session se clora à la reconnexion."}rendreOuverture(){return B`
      <h2 class="titre">Nouvelle session de courses</h2>
      <p class="explication">
        Choisissez le magasin : les scans partiront au panier au lieu d’aller directement au rangement.
      </p>

      ${this.magasins.length?B`
        <div class="pastilles">
          ${this.magasins.map(e=>B`
            <button class="pastille ${this.magasinRetenu===e?"choisie":""}"
              aria-pressed=${this.magasinRetenu===e?"true":"false"}
              @click=${()=>{this.magasinChoisi=e,this.magasinSaisi=""}}>
              ${e}
            </button>
          `)}
        </div>`:V}

      ${this.erreurMagasins?B`<p class="erreur">${this.erreurMagasins}</p>`:V}

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
      ${i>0?B`
        <p class="restantes">
          ${i} ligne${i>1?"s":""} pas encore rangée${i>1?"s":""}.
          Clore la session les abandonne : rien n’entrera en stock pour elles.
        </p>`:V}

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
      `:V}
      ${this.donnees?this.rendreCloture(this.donnees):this.rendreOuverture()}
      ${this.message?B`<p class="message">${this.message}</p>`:V}
    `}};function je(e,t){const i=new Date(t.getFullYear(),t.getMonth(),t.getDate()+e);return`${String(i.getFullYear()).padStart(4,"0")}-${String(i.getMonth()+1).padStart(2,"0")}-${String(i.getDate()).padStart(2,"0")}`}Re.styles=o`
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
  `,e([de({attribute:!1})],Re.prototype,"donnees",void 0),e([de({attribute:!1})],Re.prototype,"connexion",void 0),e([de({attribute:!1})],Re.prototype,"file",void 0),e([de({attribute:!1})],Re.prototype,"enAttente",void 0),e([he()],Re.prototype,"magasins",void 0),e([he()],Re.prototype,"magasinChoisi",void 0),e([he()],Re.prototype,"magasinSaisi",void 0),e([he()],Re.prototype,"erreurMagasins",void 0),e([he()],Re.prototype,"clotureArmee",void 0),e([he()],Re.prototype,"enCours",void 0),e([he()],Re.prototype,"message",void 0),Re=e([ce("home-stock-session")],Re);let Fe=class extends ae{constructor(){super(...arguments),this.lignes=[],this.enAttente=0,this.emplacements=[],this.erreurEmplacements=null,this.emplacementChoisi={},this.enCours=new Set,this.aEuDesLignes=!1,this.termineEnvoye=!1}connectedCallback(){super.connectedCallback(),this.chargerEmplacements()}willUpdate(e){e.has("lignes")&&this.lignes.length>0&&(this.aEuDesLignes=!0)}updated(){this.aEuDesLignes&&0===this.lignes.length&&!this.termineEnvoye&&(this.termineEnvoye=!0,this.dispatchEvent(new CustomEvent("termine",{bubbles:!0,composed:!0})))}async chargerEmplacements(){if(this.connexion){this.erreurEmplacements=null;try{const e=await this.connexion.appeler("home_stock/locations/list");this.emplacements=e.locations}catch{this.erreurEmplacements="Impossible de récupérer les emplacements. Vérifiez la connexion."}}}emplacementPour(e){const t=this.emplacementChoisi[String(e.id)];return void 0!==t?t:e.default_location_id}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()),i.sort.then(e=>"envoyee"===e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}ranger(e,t){const i=this.emplacementPour(e);if(null===i)return;const r=String(e.id);if(this.enCours.has(r))return;this.enCours=new Set(this.enCours).add(r);const s=()=>{const e=new Set(this.enCours);e.delete(r),this.enCours=e};"session"===e.source?this.ecrire("home_stock/session/store_line",{line_id:e.id,location_id:i,best_before:t.date}).then(s):this.ecrire("home_stock/stock/add",{article_id:e.article_id,quantity:e.quantity,location_id:i,best_before:t.date,price_per_base_unit:e.unit_price,idempotency_key:`rangement:${e.id}`}).then(t=>{s(),t&&this.dispatchEvent(new CustomEvent("ligne-autonome-rangee",{detail:{id:e.id},bubbles:!0,composed:!0}))})}rendreLigne(e){const t=String(e.id),i=this.enCours.has(t),r=this.emplacementPour(e),s=function(e,t){const i=[];t&&t>0&&i.push({libelle:`+${t} j (habituel)`,date:je(t,e)}),i.push({libelle:"+3 j",date:je(3,e)},{libelle:"+1 sem",date:je(7,e)},{libelle:"+1 mois",date:je(31,e)});const r=new Set,s=i.filter(e=>e.date&&!r.has(e.date)&&r.add(e.date));return[...s,{libelle:"Sans DLC",date:null}]}(new Date,e.default_shelf_life_days);return B`
      <article class="ligne">
        ${e.image?B`<img class="image" src=${e.image} alt="" />`:V}
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
              `:V}
              ${this.emplacements.map(e=>B`
                <option value=${String(e.id)} ?selected=${e.id===r}>${e.name}</option>
              `)}
            </select>
          </label>
          ${null===r?B`
            <p class="emplacement-manquant">Choisissez un emplacement avant de ranger.</p>
          `:V}
          ${this.erreurEmplacements?B`<p class="erreur">${this.erreurEmplacements}</p>`:V}
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
      `:V}
      ${e.map(e=>B`
        <section class="emplacement">
          <h3 class="emplacement-nom">${e.nom}</h3>
          ${e.lignes.map(e=>this.rendreLigne(e))}
        </section>
      `)}
    `}};function Ne(e){const t=e.trim();if(""===t)return{ok:!0,valeur:null};const i=Number(t.replace(",","."));return Number.isFinite(i)?{ok:!0,valeur:i}:{ok:!1}}function Me(e){return(Math.round(100*e)/100).toString().replace(".",",")}function Le(e){return{name:e.name,aisle_id:null!==e.aisle_id?String(e.aisle_id):"",default_location_id:null!==e.default_location_id?String(e.default_location_id):"",min_quantity:null!==e.min_quantity?String(e.min_quantity):"",default_shelf_life_days:null!==e.default_shelf_life_days?String(e.default_shelf_life_days):""}}function Oe(e){const t=e.trim();return""===t?null:Number(t)}Fe.styles=o`
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
  `,e([de({attribute:!1})],Fe.prototype,"lignes",void 0),e([de({attribute:!1})],Fe.prototype,"connexion",void 0),e([de({attribute:!1})],Fe.prototype,"file",void 0),e([de({attribute:!1})],Fe.prototype,"enAttente",void 0),e([he()],Fe.prototype,"emplacements",void 0),e([he()],Fe.prototype,"erreurEmplacements",void 0),e([he()],Fe.prototype,"emplacementChoisi",void 0),e([he()],Fe.prototype,"enCours",void 0),Fe=e([ce("home-stock-rangement")],Fe);const Ue={min_quantity:"Seuil de réapprovisionnement",default_shelf_life_days:"Durée de conservation"};function Te(e,t,i,r){const s=Ne(t[e]);return s.ok?(s.valeur!==i[e]&&(r[e]=s.valeur),null):`${Ue[e]} : nombre invalide (« ${t[e]} »).`}let De=class extends ae{constructor(){super(...arguments),this.enAttente=0,this.produits=[],this.rayons=[],this.emplacements=[],this.quantitesParProduit={},this.erreurChargement=null,this.recherche="",this.produitEditeId=null,this.produitEnEdition=null,this.brouillon=null,this.erreurEdition=null,this.enCours=!1,this.enAttenteEnvoi=!1,this.nomRayon=e=>null===e?"Sans rayon":this.rayons.find(t=>t.id===e)?.name??"Sans rayon"}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(this.connexion){this.erreurChargement=null;try{const[e,t,i,r]=await Promise.all([this.connexion.appeler("home_stock/products/list"),this.connexion.appeler("home_stock/aisles/list"),this.connexion.appeler("home_stock/locations/list"),this.connexion.appeler("home_stock/batches/list")]);this.produits=e.products,this.rayons=t.aisles,this.emplacements=i.locations;const s={};for(const e of r.batches)s[e.product_id]=(s[e.product_id]??0)+e.remaining;this.quantitesParProduit=s}catch{this.erreurChargement="Impossible de récupérer le catalogue. Vérifiez la connexion."}}}nomEmplacement(e){return null===e?"Aucun":this.emplacements.find(t=>t.id===e)?.name??"Aucun"}get produitsFiltres(){return function(e,t,i){const r=t.trim().toLowerCase();return r?e.filter(e=>e.name.toLowerCase().includes(r)||i(e.aisle_id).toLowerCase().includes(r)):e}(this.produits,this.recherche,this.nomRayon)}async ouvrirEdition(e){if(this.produitEditeId=e.id,this.produitEnEdition=e,this.brouillon=Le(e),this.erreurEdition=null,this.enAttenteEnvoi=!1,this.connexion)try{const t=await this.connexion.appeler("home_stock/product/get",{product_id:e.id});this.produitEditeId===e.id&&(this.produitEnEdition=t.product,this.brouillon=Le(t.product))}catch{}}fermerEdition(){this.produitEditeId=null,this.produitEnEdition=null,this.brouillon=null,this.erreurEdition=null,this.enAttenteEnvoi=!1}modifierBrouillon(e,t){this.brouillon&&(this.brouillon={...this.brouillon,[e]:t})}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile()),i.sort.then(e=>"envoyee"===e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}mangerProduit(e){this.dispatchEvent(new CustomEvent("manger-produit",{detail:{product_id:e.id},bubbles:!0,composed:!0}))}async enregistrer(){const e=this.produitEnEdition,t=this.brouillon;if(!e||!t||this.enCours)return;const i=function(e,t){const i={},r=e.name.trim();r&&r!==t.name&&(i.name=r),Oe(e.aisle_id)!==t.aisle_id&&(i.aisle_id=Oe(e.aisle_id)),Oe(e.default_location_id)!==t.default_location_id&&(i.default_location_id=Oe(e.default_location_id));const s=Te("min_quantity",e,t,i);if(s)return{ok:!1,erreur:s};const n=Te("default_shelf_life_days",e,t,i);return n?{ok:!1,erreur:n}:{ok:!0,champs:i}}(t,e);if(!i.ok)return void(this.erreurEdition=i.erreur);if(0===Object.keys(i.champs).length)return void this.fermerEdition();this.enCours=!0,this.erreurEdition=null,this.enAttenteEnvoi=!1;const r=await this.ecrire("home_stock/product/update",{product_id:e.id,fields:i.champs});this.enCours=!1,r?(await this.charger(),this.fermerEdition()):this.enAttenteEnvoi=!0}rendreEdition(e){const t=this.brouillon;return t?B`
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
        `:V}
        ${this.erreurEdition?B`<p class="erreur">${this.erreurEdition}</p>`:V}
        <div class="actions-edition">
          <button class="enregistrer" ?disabled=${this.enCours} @click=${this.enregistrer}>
            ${this.enCours?"Enregistrement…":"Enregistrer"}
          </button>
          <button class="annuler" ?disabled=${this.enCours} @click=${()=>this.fermerEdition()}>Annuler</button>
        </div>
      </div>
    `:V}rendreLigne(e){const t=this.quantitesParProduit[e.id]??0,i="piece"!==e.base_unit?` ${e.base_unit}`:"";return B`
      <article class="ligne">
        <div class="infos">
          <p class="nom">${e.name}</p>
          <p class="meta">
            ${this.nomRayon(e.aisle_id)} · en stock : ${t}${i}
            ${null!==e.min_quantity?B` · seuil : ${e.min_quantity}${i}`:V}
            · emplacement : ${this.nomEmplacement(e.default_location_id)}
          </p>
        </div>
        <button class="manger" @click=${()=>this.mangerProduit(e)}>Manger</button>
        <button class="modifier" @click=${()=>this.ouvrirEdition(e)}>Modifier</button>
        ${this.produitEditeId===e.id?this.rendreEdition(this.produitEnEdition??e):V}
      </article>
    `}render(){return B`
      <input class="recherche" type="search" placeholder="Rechercher un produit ou un rayon…"
        .value=${this.recherche}
        @input=${e=>{this.recherche=e.target.value}} />

      ${this.enAttente>0?B`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:V}

      ${this.erreurChargement?B`
        <p class="erreur">${this.erreurChargement}</p>
        <button class="reessayer" @click=${()=>{this.charger()}}>Réessayer</button>
      `:V}

      ${this.erreurChargement||0!==this.produitsFiltres.length?V:B`
        <p class="vide">Aucun produit.</p>
      `}

      <div class="liste">
        ${this.produitsFiltres.map(e=>this.rendreLigne(e))}
      </div>
    `}};De.styles=o`
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
  `,e([de({attribute:!1})],De.prototype,"connexion",void 0),e([de({attribute:!1})],De.prototype,"file",void 0),e([de({attribute:!1})],De.prototype,"enAttente",void 0),e([he()],De.prototype,"produits",void 0),e([he()],De.prototype,"rayons",void 0),e([he()],De.prototype,"emplacements",void 0),e([he()],De.prototype,"quantitesParProduit",void 0),e([he()],De.prototype,"erreurChargement",void 0),e([he()],De.prototype,"recherche",void 0),e([he()],De.prototype,"produitEditeId",void 0),e([he()],De.prototype,"produitEnEdition",void 0),e([he()],De.prototype,"brouillon",void 0),e([he()],De.prototype,"erreurEdition",void 0),e([he()],De.prototype,"enCours",void 0),e([he()],De.prototype,"enAttenteEnvoi",void 0),De=e([ce("home-stock-catalogue")],De);const Ie=new Set(["Une resynchronisation Open Food Facts est déjà en cours."]);let Be=class extends ae{constructor(){super(...arguments),this.enAttente=0,this.rayons=[],this.emplacements=[],this.erreurChargement=null,this.resyncEnCours=!1,this.messageResync=null,this.erreurResync=null}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(this.connexion){this.erreurChargement=null;try{const[e,t]=await Promise.all([this.connexion.appeler("home_stock/aisles/list"),this.connexion.appeler("home_stock/locations/list")]);this.rayons=e.aisles,this.emplacements=t.locations}catch{this.erreurChargement="Impossible de récupérer les rayons et les emplacements. Vérifiez la connexion."}}}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}async deplacerRayon(e,t){const i=function(e,t,i){const r=t+i;if(r<0||r>=e.length)return null;const s=[...e];return[s[t],s[r]]=[s[r],s[t]],s}(this.rayons,e,t);if(null===i)return;if(this.rayons=i,!this.file)return;const r=this.file.ajouter("home_stock/aisles/reorder",{aisle_ids:i.map(e=>e.id)});this.avertirFile(),await this.file.rejouer(),this.avertirFile(),"refusee"===await r.sort&&await this.charger()}async resynchroniser(){if(this.connexion&&!this.resyncEnCours){this.resyncEnCours=!0,this.messageResync=null,this.erreurResync=null;try{await this.connexion.appelerService("home_stock","resync_off",{all:!0}),this.messageResync="Resynchronisation lancée en tâche de fond — environ 40 minutes pour tout le catalogue. Les champs corrigés à la main ne sont jamais écrasés."}catch(e){this.erreurResync=function(e){const t=e&&"object"==typeof e&&"message"in e&&"string"==typeof e.message?e.message:null;return null!==t&&Ie.has(t)?t:"La resynchronisation n'a pas pu être lancée."}(e)}finally{this.resyncEnCours=!1}}}rendreRayons(){return 0===this.rayons.length?B`<p class="vide">Aucun rayon.</p>`:B`
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
      `:V}

      ${this.erreurChargement?B`
        <p class="erreur">${this.erreurChargement}</p>
        <button class="reessayer" @click=${()=>{this.charger()}}>Réessayer</button>
      `:V}

      <section class="section">
        <h3 class="titre">Ordre des rayons</h3>
        <p class="explication">
          L'ordre du parcours en magasin — utilisé pour trier le panier. Pas de glisser-déposer :
          « monter » et « descendre » déplacent un rayon d'un cran.
        </p>
        ${this.rendreRayons()}
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
        ${this.messageResync?B`<p class="message-resync">${this.messageResync}</p>`:V}
        ${this.erreurResync?B`<p class="erreur">${this.erreurResync}</p>`:V}
      </section>
    `}};function He(e,t){return"piece"===t?`${Me(e)} pièce${e>=2?"s":""}`:"g"===t?e>=1e3?`${Me(e/1e3)} kg`:`${Me(e)} g`:e>=1e3?`${Me(e/1e3)} l`:`${Me(e)} ml`}Be.styles=o`
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
  `,e([de({attribute:!1})],Be.prototype,"connexion",void 0),e([de({attribute:!1})],Be.prototype,"file",void 0),e([de({attribute:!1})],Be.prototype,"enAttente",void 0),e([he()],Be.prototype,"rayons",void 0),e([he()],Be.prototype,"emplacements",void 0),e([he()],Be.prototype,"erreurChargement",void 0),e([he()],Be.prototype,"resyncEnCours",void 0),e([he()],Be.prototype,"messageResync",void 0),e([he()],Be.prototype,"erreurResync",void 0),Be=e([ce("home-stock-reglages")],Be);const Ve={consumption:"Mangé",waste:"Jeté",expired:"Périmé"};let Je=class extends ae{constructor(){super(...arguments),this.productId=null,this.produit=null,this.lot=null,this.portion=null,this.quantite=null,this.motif="consumption",this.partage=!1,this.partsTotal=2,this.partsMoi=1,this.erreur=null,this.enCours=!1,this.enAttenteEnvoi=!1,this.texteQuantite=""}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(!this.connexion||null===this.productId)return;const e=await this.connexion.appeler("home_stock/product/get",{product_id:this.productId});this.produit=e.produit??e.product,this.lot=e.next_batch,this.portion=e.suggested_portion,this.quantite="piece"===this.produit?.base_unit&&this.lot?1:null,this.texteQuantite=null===this.quantite?"":String(this.quantite)}saisirQuantite(e){this.texteQuantite=e;const t=Ne(e);if(!t.ok)return this.erreur="Quantité : ce n’est pas un nombre.",void(this.quantite=null);this.erreur=null,this.quantite=t.valeur}choisirRaccourci(e){this.erreur=null,this.quantite=e,this.texteQuantite=String(e)}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}async enregistrer(){if(this.enCours||!this.file||!this.lot||null===this.produit)return;if(null===this.quantite||!(this.quantite>0))return void(this.erreur="Quantité : donne un nombre supérieur à zéro.");const e=this.partage&&"consumption"===this.motif;if(e&&!(this.partsTotal>=1&&this.partsTotal<=24&&this.partsMoi>=0&&this.partsMoi<=this.partsTotal))return void(this.erreur=this.partsTotal>24?"On ne sert pas plus de 24 parts.":"On ne mange pas plus de parts qu’il n’en a été servi.");this.erreur=null,this.enCours=!0,this.enAttenteEnvoi=!1;const t={product_id:this.produit.id,quantity:this.quantite,reason:this.motif};this.quantite<=this.lot.remaining&&(t.batch_id=this.lot.id),e&&(t.parts_total=this.partsTotal,t.parts_mine=this.partsMoi);const i=this.file.ajouter("home_stock/stock/consume",t);this.avertirFile(),this.file.rejouer().then(()=>this.avertirFile());const r=await i.sort;this.enCours=!1,"envoyee"===r?this.dispatchEvent(new CustomEvent("consommation-enregistree",{bubbles:!0,composed:!0})):"en-attente"===r&&(this.enAttenteEnvoi=!0)}rendreMotifs(){return B`
      <section class="motifs">
        ${Object.keys(Ve).map(e=>B`
          <button type="button" class="motif ${this.motif===e?"motif-actif":""}"
            @click=${()=>{this.motif=e}}>
            ${Ve[e]}
          </button>
        `)}
      </section>
    `}rendreParts(){return"consumption"!==this.motif?V:B`
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
          </div>`:V}
      </section>
    `}render(){if(!this.produit)return V;if(!this.lot)return B`
        <section class="entete">
          <h2 class="nom">${this.produit.name}</h2>
        </section>
        <p class="plus-rien">Plus rien en stock.</p>
      `;const e=function(e,t,i){if(e<=0)return[];const r=[];"piece"===t?r.push({libelle:He(1,t),quantite:1}):null!==i&&i>0&&i<=e&&r.push({libelle:`1 portion (${He(i,t)})`,quantite:i}),"piece"!==t&&r.push({libelle:`La moitié (${He(e/2,t)})`,quantite:e/2}),r.push({libelle:`Tout le reste (${He(e,t)})`,quantite:e});const s=new Set;return r.filter(t=>t.quantite<=e&&!s.has(t.quantite)&&s.add(t.quantite))}(this.lot.remaining,this.produit.base_unit,this.portion);return B`
      <section class="entete">
        <h2 class="nom">${this.produit.name}</h2>
        <p class="reste">
          Reste ${t=this.lot.remaining,i=this.produit.base_unit,"piece"===i?`${Me(t)} pièce${t>=2?"s":""}`:`${Me(t)} ${i}`} sur le lot visé
          ${this.lot.best_before?B` — DLC ${function(e){const t=/^(\d{4})-(\d{2})-(\d{2})$/.exec(e);return t?`${t[3]}/${t[2]}/${t[1]}`:e}(this.lot.best_before)}`:V}
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

      ${this.erreur?B`<p class="erreur">${this.erreur}</p>`:V}
      ${this.enAttenteEnvoi?B`
        <p class="en-attente">Pas encore envoyé — ça repartira dès que le réseau revient.</p>
      `:V}

      <button type="button" class="enregistrer" ?disabled=${this.enCours} @click=${this.enregistrer}>
        ${Ve[this.motif]}
      </button>
    `;var t,i}};Je.styles=o`
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
  `,e([de({attribute:!1})],Je.prototype,"connexion",void 0),e([de({attribute:!1})],Je.prototype,"file",void 0),e([de({type:Number})],Je.prototype,"productId",void 0),e([he()],Je.prototype,"produit",void 0),e([he()],Je.prototype,"lot",void 0),e([he()],Je.prototype,"portion",void 0),e([he()],Je.prototype,"quantite",void 0),e([he()],Je.prototype,"motif",void 0),e([he()],Je.prototype,"partage",void 0),e([he()],Je.prototype,"partsTotal",void 0),e([he()],Je.prototype,"partsMoi",void 0),e([he()],Je.prototype,"erreur",void 0),e([he()],Je.prototype,"enCours",void 0),e([he()],Je.prototype,"enAttenteEnvoi",void 0),e([he()],Je.prototype,"texteQuantite",void 0),Je=e([ce("home-stock-consommation")],Je);const Qe={day:14,week:12,month:12},We={day:"Jours",week:"Semaines",month:"Mois"};function Ye(e){return`${e.toFixed(2).replace(".",",")} €`}let Ge=class extends ae{constructor(){super(...arguments),this.jour=null,this.serie=null,this.granularite="day",this.enCours=!1,this.seauSelectionne=null}connectedCallback(){super.connectedCallback(),this.chargerJour(),this.chargerSerie(this.granularite)}async chargerJour(e){this.connexion&&(this.jour=await this.connexion.appeler("home_stock/journal/day",e?{date:e}:{}))}async chargerSerie(e){if(this.connexion){this.enCours=!0;try{this.serie=await this.connexion.appeler("home_stock/journal/series",{granularity:e,count:Qe[e]})}finally{this.enCours=!1}}}async choisirGranularite(e){this.granularite=e,this.seauSelectionne=null,await this.chargerSerie(e)}async ouvrirSeau(e){"day"===this.granularite?(this.seauSelectionne=null,await this.chargerJour(e.label)):(this.jour=null,this.seauSelectionne=e)}partDeLaBarre(e,t){return t>0?e/t:0}rendreBarres(){const e=this.serie?.buckets??[],t=Math.max(0,...e.map(e=>e.kcal));return B`
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
        ${Object.keys(We).map(e=>B`
          <button type="button" class="granularite ${this.granularite===e?"granularite-active":""}"
            @click=${()=>this.choisirGranularite(e)}>
            ${We[e]}
          </button>
        `)}
      </nav>
    `}rendreEntree(e){const t=null!==e.parts_total&&e.parts_total!==e.parts_mine;return B`
      <li class="entree ${"consumption"!==e.reason?"jete":""}">
        <span class="entree-nom">${e.product_name}</span>
        <span class="entree-quantite">
          ${Me(Math.abs(e.quantity))} ${e.base_unit}
        </span>
        ${t?B`<span class="entree-parts">${e.parts_mine??0}/${e.parts_total}</span>`:V}
        <span class="entree-kcal">${null===e.kcal?"—":`${Math.round(e.kcal)} kcal`}</span>
      </li>
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
          ${Ye(e.totals.cost)}
          ${e.totals.waste_cost>0?B` — dont ${Ye(e.totals.waste_cost)} jeté`:V}
        </p>
        ${e.totals.unvalued>0?B`
          <p class="non-chiffre">${e.totals.unvalued} sortie(s) sans calories connues.</p>
        `:V}
      </section>
    `:V}rendreSeauTotaux(){const e=this.seauSelectionne;return e?B`
      <section class="jour">
        <h2 class="titre-jour">${e.label}</h2>
        <p class="total-kcal">${Math.round(e.kcal)} kcal</p>
        <p class="total-cout">
          ${Ye(e.cost)}
          ${e.waste_cost>0?B` — dont ${Ye(e.waste_cost)} jeté`:V}
        </p>
      </section>
    `:V}render(){return B`
      <h1 class="titre">Journal</h1>
      ${this.rendreGranularites()}
      ${this.rendreBarres()}
      ${"day"===this.granularite?this.rendreJour():this.rendreSeauTotaux()}
    `}};Ge.styles=o`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .titre { margin: 0 0 8px; font-size: 1.2rem; }
    .granularites { display: flex; gap: 8px; margin-bottom: 8px; }
    .granularite {
      flex: 1 1 auto; min-height: 48px; border-radius: 8px; border: none; font-size: 0.9rem;
      background: var(--secondary-background-color); color: var(--primary-text-color);
    }
    .granularite-active { background: var(--primary-color); color: var(--text-primary-color, #fff); }
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
  `,e([de({attribute:!1})],Ge.prototype,"connexion",void 0),e([he()],Ge.prototype,"jour",void 0),e([he()],Ge.prototype,"serie",void 0),e([he()],Ge.prototype,"granularite",void 0),e([he()],Ge.prototype,"enCours",void 0),e([he()],Ge.prototype,"seauSelectionne",void 0),Ge=e([ce("home-stock-journal")],Ge);const Ke={install:"posée",charge:"rechargée",replacement:"changée",removal:"retirée"};function Ze(e){return e.orphaned?"entité introuvable":null===e.last_percent?"jamais relevée":"unavailable"===e.state||"unknown"===e.state?`${Math.trunc(e.last_percent)} % — muette depuis le dernier relevé`:`${Math.trunc(e.last_percent)} %`}function Xe(e){if(!e.spare_label)return null;const t="built_in"!==e.kind,i=e.spare_in_stock??0,r=i>0?`${Number.isInteger(i)?i:i.toFixed(1)} en stock`:(t?"aucune":"aucun")+" en stock";return`${e.cell_count}× ${e.spare_label}, ${r}`}let et=class extends ae{constructor(){super(...arguments),this.piles=[],this.aDeclarer=[],this.selection=null,this.evenements=[],this.armee=null,this.refus=null,this.ignoree=null,this.motif="",this.erreurMotif=null}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(!this.connexion)return;const[e,t]=await Promise.all([this.connexion.appeler("home_stock/batteries/list"),this.connexion.appeler("home_stock/batteries/discover")]);this.piles=[...e.batteries].sort((e,t)=>(e.last_percent??Number.POSITIVE_INFINITY)-(t.last_percent??Number.POSITIVE_INFINITY)||e.label.localeCompare(t.label)),this.aDeclarer=t.sensors}async ecrire(e,t){if(!this.file)return;const i=this.file.ajouter(e,t);return this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0})),this.file.rejouer().then(()=>{this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}),i.reponse}async ouvrir(e){if(this.selection=e.id,this.armee=null,this.refus=null,this.evenements=[],!this.connexion)return;const t=await this.connexion.appeler("home_stock/battery/events",{battery_id:e.id});this.evenements=t.events}async surEvenement(e){const t="built_in"===e.kind||"rechargeable_cell"===e.kind?"charge":"replacement",i=`${e.id}:${t}`;if(this.armee!==i)return void(this.armee=i);this.armee=null;const r=await this.ecrire("home_stock/battery/event",{battery_id:e.id,kind:t});this.refus=r?.spare_refused??null,await this.charger()}async suivre(e){await this.ecrire("home_stock/battery/declare",{label:e.device_name||e.entity_id,kind:"primary",entity_registry_id:e.entity_registry_id,device_id:e.device_id,tracked:!0}),await this.charger()}async confirmerIgnorer(){const e=this.ignoree;e&&(this.motif.trim()?(this.erreurMotif=null,await this.ecrire("home_stock/battery/declare",{label:e.device_name||e.entity_id,kind:"primary",entity_registry_id:e.entity_registry_id,device_id:e.device_id,tracked:!1,exclusion_reason:this.motif.trim()}),this.ignoree=null,this.motif="",await this.charger()):this.erreurMotif="Un motif est nécessaire pour ignorer une pile.")}rendreADeclarer(){return 0===this.aDeclarer.length?V:B`
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
          ${this.erreurMotif?B`<p class="erreur">${this.erreurMotif}</p>`:V}
          <button class="action confirmer-ignorer" @click=${()=>this.confirmerIgnorer()}>
            Confirmer et ignorer
          </button>
        `:V}
      </section>
    `}rendreFiche(e){const t="built_in"===e.kind||"rechargeable_cell"===e.kind?"charge":"replacement",i=this.armee===`${e.id}:${t}`,r="charge"===t?"de la recharger":"de la changer";return B`
      <section class="section">
        <h2>${e.label}</h2>
        <span class="detail">${e.verb} — ${Ze(e)}</span>
        ${Xe(e)?B`<span class="detail">${Xe(e)}</span>`:V}
        <span class="detail">Seuils : ${e.low_percent} % / ${e.keep_percent} %</span>
        ${e.entity_id?B`<span class="detail">${e.entity_id}</span>`:V}
        <button class="action evenement" @click=${()=>this.surEvenement(e)}>
          ${i?`Confirmer : je viens ${r}`:`Je viens ${r}`}
        </button>
        ${this.refus?B`<p class="refus">${this.refus}</p>`:V}
        <h2>Historique</h2>
        ${0===this.evenements.length?B`<span class="detail">Aucun événement enregistré.</span>`:this.evenements.map(e=>B`
              <span class="evenement-passe">
                ${function(e){const t=new Date(e);if(Number.isNaN(t.getTime()))return e;const i=e=>String(e).padStart(2,"0");return`${i(t.getDate())}/${i(t.getMonth()+1)}/${t.getFullYear()}`}(e.occurred_at)} — ${Ke[e.kind]??e.kind}
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
            <span class="detail">${Ze(e)}</span>
            ${Xe(e)?B`<span class="detail">${Xe(e)}</span>`:V}
          </button>
        `)}
      </section>
    `}};et.styles=o`
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
  `,e([de({attribute:!1})],et.prototype,"connexion",void 0),e([de({attribute:!1})],et.prototype,"file",void 0),e([he()],et.prototype,"piles",void 0),e([he()],et.prototype,"aDeclarer",void 0),e([he()],et.prototype,"selection",void 0),e([he()],et.prototype,"evenements",void 0),e([he()],et.prototype,"armee",void 0),e([he()],et.prototype,"refus",void 0),e([he()],et.prototype,"ignoree",void 0),e([he()],et.prototype,"motif",void 0),e([he()],et.prototype,"erreurMotif",void 0),et=e([ce("home-stock-piles")],et);const tt="Sans emplacement";function it(e){const[t,i,r]=e.split("-");return`${r}/${i}/${t}`}function rt(e){return e.warranty_ends_on&&null!==e.days_left?e.days_left<0?`garantie terminée depuis le ${it(e.warranty_ends_on)}`:`garantie jusqu’au ${it(e.warranty_ends_on)} — ${e.days_left} jours`:"garantie non renseignée"}let st=class extends ae{constructor(){super(...arguments),this.equipements=[],this.fiche=null,this.armee=null}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(!this.connexion)return;const e=await this.connexion.appeler("home_stock/equipment/list");this.equipements=e.equipment}async ouvrir(e){if(!this.connexion)return;this.armee=null;const t=await this.connexion.appeler("home_stock/equipment/get",{equipment_id:e.id});this.fiche=t.equipment}async delier(e){this.armee===e.id?(this.armee=null,this.file&&(this.file.ajouter("home_stock/equipment/consumable/unlink",{consumable_id:e.id}),this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0})),await this.file.rejouer(),this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0})),this.fiche&&await this.ouvrir(this.fiche))):this.armee=e.id}groupes(){const e=new Map;for(const t of this.equipements){const i=t.location_name??tt;e.set(i,[...e.get(i)??[],t])}return[...e.entries()].sort(([e],[t])=>e===tt?1:t===tt?-1:e.localeCompare(t))}rendreFiche(e){return B`
      <section class="section">
        <h2>${e.name}</h2>
        <span class="detail">${e.location_name??tt}</span>
        ${e.brand||e.model?B`
          <span class="detail">${[e.brand,e.model].filter(Boolean).join(" ")}</span>`:V}
        ${e.serial?B`<span class="detail">N° de série : ${e.serial}</span>`:V}
        ${e.purchased_on?B`<span class="detail">Acheté le ${it(e.purchased_on)}</span>`:B`<span class="detail">Date d’achat non renseignée</span>`}
        <span class="detail">${rt(e)}</span>
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
                  </span>`:V}
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
              <span class="detail">${rt(e)}</span>
              ${e.consumable_count?B`<span class="detail">${e.consumable_count} consommable(s)</span>`:V}
            </button>
          `)}
        </section>
      `)}
    `}};st.styles=o`
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
  `,e([de({attribute:!1})],st.prototype,"connexion",void 0),e([de({attribute:!1})],st.prototype,"file",void 0),e([he()],st.prototype,"equipements",void 0),e([he()],st.prototype,"fiche",void 0),e([he()],st.prototype,"armee",void 0),st=e([ce("home-stock-equipements")],st);let nt=class extends ae{constructor(){super(...arguments),this.narrow=!1,this.ecran="scanner",this.enAttente=0,this.session=null,this.resultatCourant=null,this.derniereFiche=null,this.enAttenteRangement=[],this.erreurFile=null,this.navigationArmee=null,this.produitAManger=null,this.auRetourDuReseau=()=>{this.file?.rejouer().then(()=>{this.enAttente=this.file.taille()})},this.surCodeLu=async e=>{try{const t=await this.connexion.appeler("home_stock/lookup",{code:e.detail.code});this.resultatCourant=t,this.ecran="fiche"}catch{this.derniereFiche={nom:e.detail.code,marque:null,image:null,statut:"Connexion indisponible — réessayez."}}},this.surArticlePret=e=>{const{articleId:t,quantite:i,prixUnitaire:r,mode:s,offDroppedFields:n}=e.detail;if("panier"===s)return this.file.ajouter("home_stock/session/add_line",{article_id:t,quantity:i,unit_price:r}),this.enAttente=this.file.taille(),this.file.rejouer().then(()=>{this.enAttente=this.file.taille()}),this.derniereFiche=function(e,t,i=[]){return e?{nom:e.off?.label??e.article?.label??e.product?.name??e.code,marque:e.off?.brand??e.article?.brand??null,image:e.off?.image??e.article?.image??null,statut:t,ignores:i}:null}(this.resultatCourant,"Ajouté au panier.",n),this.resultatCourant=null,void(this.ecran="scanner");const o=function(e,t,i,r){return{source:"autonome",id:`autonome-${crypto.randomUUID()}`,article_id:t,quantity:i,unit_price:r,product_name:e?.product?.name??e?.off?.label??e?.article?.label??e?.off?.generic_name??"Article",base_unit:e?.product?.base_unit??"piece",default_location_id:e?.product?.default_location_id??null,default_shelf_life_days:e?.product?.default_shelf_life_days??null,brand:e?.off?.brand??e?.article?.brand??null,image:e?.off?.image??e?.article?.image??null,net_quantity:e?.article?.net_quantity??e?.off?.net_quantity??null}}(this.resultatCourant,t,i,r);this.enAttenteRangement=[...this.enAttenteRangement,o],this.resultatCourant=null,this.ecran="rangement"},this.surSessionChangee=async()=>{await this.actualiserSession(),this.ecran="scanner"},this.surMangerProduit=e=>{this.produitAManger=e.detail.product_id,this.demanderNavigation("consommation")},this.surConsommationEnregistree=()=>{this.produitAManger=null,this.ecran="scanner"},this.surLigneAutonomeRangee=e=>{this.enAttenteRangement=this.enAttenteRangement.filter(t=>t.id!==e.detail.id)},this.surRangementTermine=()=>{this.navigationArmee=null,this.ecran="scanner"},this.surFileChangee=()=>{this.enAttente=this.file.taille()}}connectedCallback(){super.connectedCallback(),this.connexion=new me(this.hass),this.file=new ye(window.localStorage,(e,t)=>this.connexion.appeler(e,t),(e,t)=>{this.erreurFile=t}),this.enAttente=this.file.taille(),this.file.rejouer().then(()=>{this.enAttente=this.file.taille()}),this.actualiserSession(),this.connexion.abonner(()=>{this.actualiserSession(),this.requestUpdate()}).then(e=>{this.isConnected?this.desabonner=e:e()}),window.addEventListener("online",this.auRetourDuReseau),this.addEventListener("manger-produit",this.surMangerProduit),this.addEventListener("consommation-enregistree",this.surConsommationEnregistree)}disconnectedCallback(){super.disconnectedCallback(),this.desabonner?.(),this.desabonner=void 0,window.removeEventListener("online",this.auRetourDuReseau),this.removeEventListener("manger-produit",this.surMangerProduit),this.removeEventListener("consommation-enregistree",this.surConsommationEnregistree)}async actualiserSession(){try{this.session=await this.connexion.appeler("home_stock/session/current")}catch{}}get lignesSessionARanger(){return this.session?.session&&"to_store"===this.session.session.state?this.session.lines.filter(e=>null===e.stored_at).map(e=>({...e,source:"session"})):[]}get lignesARanger(){return[...this.lignesSessionARanger,...this.enAttenteRangement]}demanderNavigation(e){"rangement"===this.ecran&&"rangement"!==e&&this.enAttenteRangement.length>0?this.navigationArmee=e:this.ecran=e}confirmerNavigation(){const e=this.navigationArmee;this.navigationArmee=null,e&&(this.ecran=e)}annulerNavigation(){this.navigationArmee=null}rendreNavigation(){if("fiche"===this.ecran)return V;if(this.navigationArmee)return B`
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
        `:V}
        ${e&&"panier"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("panier")}>
            Panier${this.session.totals.lines?` (${this.session.totals.lines})`:""}
          </button>
        `:V}
        ${t.length>0&&"rangement"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("rangement")}>
            Ranger (${t.length})
          </button>
        `:V}
        ${"session"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("session")}>
            Courses
          </button>
        `:V}
        ${"catalogue"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("catalogue")}>Catalogue</button>
        `:V}
        ${"journal"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("journal")}>Journal</button>
        `:V}
        ${"piles"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("piles")}>Piles</button>
        `:V}
        ${"equipements"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("equipements")}>
            Équipements
          </button>
        `:V}
        ${"reglages"!==this.ecran?B`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("reglages")}>Réglages</button>
        `:V}
      </nav>
    `}rendreErreurFile(){return this.erreurFile?B`
      <p class="erreur-file">
        ${this.erreurFile}
        <button class="fermer-erreur-file" @click=${()=>{this.erreurFile=null}}>OK</button>
      </p>
    `:V}rendreEcran(){return"fiche"===this.ecran&&this.resultatCourant?B`
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
          @session-changee=${this.surSessionChangee} @file-changee=${this.surFileChangee}>
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
        <home-stock-journal .connexion=${this.connexion}></home-stock-journal>`:"piles"===this.ecran?B`
        <home-stock-piles .connexion=${this.connexion} .file=${this.file}
          @file-changee=${this.surFileChangee}>
        </home-stock-piles>`:"equipements"===this.ecran?B`
        <home-stock-equipements .connexion=${this.connexion} .file=${this.file}
          @file-changee=${this.surFileChangee}>
        </home-stock-equipements>`:B`
      <home-stock-scanner .session=${this.session?.session?{store:this.session.session.store}:null}
        .derniereFiche=${this.derniereFiche} .enAttente=${this.enAttente} @code-lu=${this.surCodeLu}>
      </home-stock-scanner>`}render(){return B`${this.rendreNavigation()}${this.rendreErreurFile()}${this.rendreEcran()}`}};nt.styles=o`
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
  `,e([de({attribute:!1})],nt.prototype,"hass",void 0),e([de({attribute:!1})],nt.prototype,"narrow",void 0),e([he()],nt.prototype,"ecran",void 0),e([he()],nt.prototype,"enAttente",void 0),e([he()],nt.prototype,"session",void 0),e([he()],nt.prototype,"resultatCourant",void 0),e([he()],nt.prototype,"derniereFiche",void 0),e([he()],nt.prototype,"enAttenteRangement",void 0),e([he()],nt.prototype,"erreurFile",void 0),e([he()],nt.prototype,"navigationArmee",void 0),e([he()],nt.prototype,"produitAManger",void 0),nt=e([ce("home-stock-panel")],nt);export{nt as PanneauGardeManger};
