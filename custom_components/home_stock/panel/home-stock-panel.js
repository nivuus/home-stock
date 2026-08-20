function e(e,t,i,r){var n,s=arguments.length,o=s<3?t:null===r?r=Object.getOwnPropertyDescriptor(t,i):r;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)o=Reflect.decorate(e,t,i,r);else for(var a=e.length-1;a>=0;a--)(n=e[a])&&(o=(s<3?n(o):s>3?n(t,i,o):n(t,i))||o);return s>3&&o&&Object.defineProperty(t,i,o),o}"function"==typeof SuppressedError&&SuppressedError;
/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const t=globalThis,i=t.ShadowRoot&&(void 0===t.ShadyCSS||t.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,r=Symbol(),n=new WeakMap;let s=class{constructor(e,t,i){if(this._$cssResult$=!0,i!==r)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o;const t=this.t;if(i&&void 0===e){const i=void 0!==t&&1===t.length;i&&(e=n.get(t)),void 0===e&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&n.set(t,e))}return e}toString(){return this.cssText}};const o=(e,...t)=>{const i=1===e.length?e[0]:t.reduce((t,i,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if("number"==typeof e)return e;throw Error("Value passed to 'css' function must be a 'css' function result: "+e+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+e[r+1],e[0]);return new s(i,e,r)},a=i?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t="";for(const i of e.cssRules)t+=i.cssText;return(e=>new s("string"==typeof e?e:e+"",void 0,r))(t)})(e):e,{is:l,defineProperty:c,getOwnPropertyDescriptor:u,getOwnPropertyNames:d,getOwnPropertySymbols:h,getPrototypeOf:p}=Object,m=globalThis,f=m.trustedTypes,g=f?f.emptyScript:"",v=m.reactiveElementPolyfillSupport,b=(e,t)=>e,y={toAttribute(e,t){switch(t){case Boolean:e=e?g:null;break;case Object:case Array:e=null==e?e:JSON.stringify(e)}return e},fromAttribute(e,t){let i=e;switch(t){case Boolean:i=null!==e;break;case Number:i=null===e?null:Number(e);break;case Object:case Array:try{i=JSON.parse(e)}catch(e){i=null}}return i}},x=(e,t)=>!l(e,t),$={attribute:!0,type:String,converter:y,reflect:!1,useDefault:!1,hasChanged:x};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */Symbol.metadata??=Symbol("metadata"),m.litPropertyMetadata??=new WeakMap;let _=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=$){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){const i=Symbol(),r=this.getPropertyDescriptor(e,i,t);void 0!==r&&c(this.prototype,e,r)}}static getPropertyDescriptor(e,t,i){const{get:r,set:n}=u(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){const s=r?.call(this);n?.call(this,t),this.requestUpdate(e,s,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??$}static _$Ei(){if(this.hasOwnProperty(b("elementProperties")))return;const e=p(this);e.finalize(),void 0!==e.l&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(b("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(b("properties"))){const e=this.properties,t=[...d(e),...h(e)];for(const i of t)this.createProperty(i,e[i])}const e=this[Symbol.metadata];if(null!==e){const t=litPropertyMetadata.get(e);if(void 0!==t)for(const[e,i]of t)this.elementProperties.set(e,i)}this._$Eh=new Map;for(const[e,t]of this.elementProperties){const i=this._$Eu(e,t);void 0!==i&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){const t=[];if(Array.isArray(e)){const i=new Set(e.flat(1/0).reverse());for(const e of i)t.unshift(a(e))}else void 0!==e&&t.push(a(e));return t}static _$Eu(e,t){const i=t.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof e?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),void 0!==this.renderRoot&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){const e=new Map,t=this.constructor.elementProperties;for(const i of t.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){const e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((e,r)=>{if(i)e.adoptedStyleSheets=r.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(const i of r){const r=document.createElement("style"),n=t.litNonce;void 0!==n&&r.setAttribute("nonce",n),r.textContent=i.cssText,e.appendChild(r)}})(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,i){this._$AK(e,i)}_$ET(e,t){const i=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,i);if(void 0!==r&&!0===i.reflect){const n=(void 0!==i.converter?.toAttribute?i.converter:y).toAttribute(t,i.type);this._$Em=e,null==n?this.removeAttribute(r):this.setAttribute(r,n),this._$Em=null}}_$AK(e,t){const i=this.constructor,r=i._$Eh.get(e);if(void 0!==r&&this._$Em!==r){const e=i.getPropertyOptions(r),n="function"==typeof e.converter?{fromAttribute:e.converter}:void 0!==e.converter?.fromAttribute?e.converter:y;this._$Em=r;const s=n.fromAttribute(t,e.type);this[r]=s??this._$Ej?.get(r)??s,this._$Em=null}}requestUpdate(e,t,i,r=!1,n){if(void 0!==e){const s=this.constructor;if(!1===r&&(n=this[e]),i??=s.getPropertyOptions(e),!((i.hasChanged??x)(n,t)||i.useDefault&&i.reflect&&n===this._$Ej?.get(e)&&!this.hasAttribute(s._$Eu(e,i))))return;this.C(e,t,i)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:i,reflect:r,wrapped:n},s){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,s??t??this[e]),!0!==n||void 0!==s)||(this._$AL.has(e)||(this.hasUpdated||i||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}const e=this.scheduleUpdate();return null!=e&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}const e=this.constructor.elementProperties;if(e.size>0)for(const[t,i]of e){const{wrapped:e}=i,r=this[t];!0!==e||this._$AL.has(t)||void 0===r||this.C(t,void 0,i,r)}}let e=!1;const t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};_.elementStyles=[],_.shadowRootOptions={mode:"open"},_[b("elementProperties")]=new Map,_[b("finalized")]=new Map,v?.({ReactiveElement:_}),(m.reactiveElementVersions??=[]).push("2.1.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const A=globalThis,k=e=>e,C=A.trustedTypes,E=C?C.createPolicy("lit-html",{createHTML:e=>e}):void 0,w="$lit$",P=`lit$${Math.random().toFixed(9).slice(2)}$`,S="?"+P,q=`<${S}>`,R=document,z=()=>R.createComment(""),F=e=>null===e||"object"!=typeof e&&"function"!=typeof e,U=Array.isArray,N="[ \t\n\f\r]",O=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,L=/-->/g,j=/>/g,D=RegExp(`>|${N}(?:([^\\s"'>=/]+)(${N}*=${N}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),M=/'/g,T=/"/g,B=/^(?:script|style|textarea|title)$/i,H=(e=>(t,...i)=>({_$litType$:e,strings:t,values:i}))(1),I=Symbol.for("lit-noChange"),V=Symbol.for("lit-nothing"),W=new WeakMap,J=R.createTreeWalker(R,129);function Q(e,t){if(!U(e)||!e.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==E?E.createHTML(t):t}const K=(e,t)=>{const i=e.length-1,r=[];let n,s=2===t?"<svg>":3===t?"<math>":"",o=O;for(let t=0;t<i;t++){const i=e[t];let a,l,c=-1,u=0;for(;u<i.length&&(o.lastIndex=u,l=o.exec(i),null!==l);)u=o.lastIndex,o===O?"!--"===l[1]?o=L:void 0!==l[1]?o=j:void 0!==l[2]?(B.test(l[2])&&(n=RegExp("</"+l[2],"g")),o=D):void 0!==l[3]&&(o=D):o===D?">"===l[0]?(o=n??O,c=-1):void 0===l[1]?c=-2:(c=o.lastIndex-l[2].length,a=l[1],o=void 0===l[3]?D:'"'===l[3]?T:M):o===T||o===M?o=D:o===L||o===j?o=O:(o=D,n=void 0);const d=o===D&&e[t+1].startsWith("/>")?" ":"";s+=o===O?i+q:c>=0?(r.push(a),i.slice(0,c)+w+i.slice(c)+P+d):i+P+(-2===c?t:d)}return[Q(e,s+(e[i]||"<?>")+(2===t?"</svg>":3===t?"</math>":"")),r]};class Y{constructor({strings:e,_$litType$:t},i){let r;this.parts=[];let n=0,s=0;const o=e.length-1,a=this.parts,[l,c]=K(e,t);if(this.el=Y.createElement(l,i),J.currentNode=this.el.content,2===t||3===t){const e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;null!==(r=J.nextNode())&&a.length<o;){if(1===r.nodeType){if(r.hasAttributes())for(const e of r.getAttributeNames())if(e.endsWith(w)){const t=c[s++],i=r.getAttribute(e).split(P),o=/([.?@])?(.*)/.exec(t);a.push({type:1,index:n,name:o[2],strings:i,ctor:"."===o[1]?te:"?"===o[1]?ie:"@"===o[1]?re:ee}),r.removeAttribute(e)}else e.startsWith(P)&&(a.push({type:6,index:n}),r.removeAttribute(e));if(B.test(r.tagName)){const e=r.textContent.split(P),t=e.length-1;if(t>0){r.textContent=C?C.emptyScript:"";for(let i=0;i<t;i++)r.append(e[i],z()),J.nextNode(),a.push({type:2,index:++n});r.append(e[t],z())}}}else if(8===r.nodeType)if(r.data===S)a.push({type:2,index:n});else{let e=-1;for(;-1!==(e=r.data.indexOf(P,e+1));)a.push({type:7,index:n}),e+=P.length-1}n++}}static createElement(e,t){const i=R.createElement("template");return i.innerHTML=e,i}}function Z(e,t,i=e,r){if(t===I)return t;let n=void 0!==r?i._$Co?.[r]:i._$Cl;const s=F(t)?void 0:t._$litDirective$;return n?.constructor!==s&&(n?._$AO?.(!1),void 0===s?n=void 0:(n=new s(e),n._$AT(e,i,r)),void 0!==r?(i._$Co??=[])[r]=n:i._$Cl=n),void 0!==n&&(t=Z(e,n._$AS(e,t.values),n,r)),t}class G{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){const{el:{content:t},parts:i}=this._$AD,r=(e?.creationScope??R).importNode(t,!0);J.currentNode=r;let n=J.nextNode(),s=0,o=0,a=i[0];for(;void 0!==a;){if(s===a.index){let t;2===a.type?t=new X(n,n.nextSibling,this,e):1===a.type?t=new a.ctor(n,a.name,a.strings,this,e):6===a.type&&(t=new ne(n,this,e)),this._$AV.push(t),a=i[++o]}s!==a?.index&&(n=J.nextNode(),s++)}return J.currentNode=R,r}p(e){let t=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(e,i,t),t+=i.strings.length-2):i._$AI(e[t])),t++}}class X{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,i,r){this.type=2,this._$AH=V,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=i,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode;const t=this._$AM;return void 0!==t&&11===e?.nodeType&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=Z(this,e,t),F(e)?e===V||null==e||""===e?(this._$AH!==V&&this._$AR(),this._$AH=V):e!==this._$AH&&e!==I&&this._(e):void 0!==e._$litType$?this.$(e):void 0!==e.nodeType?this.T(e):(e=>U(e)||"function"==typeof e?.[Symbol.iterator])(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==V&&F(this._$AH)?this._$AA.nextSibling.data=e:this.T(R.createTextNode(e)),this._$AH=e}$(e){const{values:t,_$litType$:i}=e,r="number"==typeof i?this._$AC(e):(void 0===i.el&&(i.el=Y.createElement(Q(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===r)this._$AH.p(t);else{const e=new G(r,this),i=e.u(this.options);e.p(t),this.T(i),this._$AH=e}}_$AC(e){let t=W.get(e.strings);return void 0===t&&W.set(e.strings,t=new Y(e)),t}k(e){U(this._$AH)||(this._$AH=[],this._$AR());const t=this._$AH;let i,r=0;for(const n of e)r===t.length?t.push(i=new X(this.O(z()),this.O(z()),this,this.options)):i=t[r],i._$AI(n),r++;r<t.length&&(this._$AR(i&&i._$AB.nextSibling,r),t.length=r)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){const t=k(e).nextSibling;k(e).remove(),e=t}}setConnected(e){void 0===this._$AM&&(this._$Cv=e,this._$AP?.(e))}}class ee{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,i,r,n){this.type=1,this._$AH=V,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=n,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=V}_$AI(e,t=this,i,r){const n=this.strings;let s=!1;if(void 0===n)e=Z(this,e,t,0),s=!F(e)||e!==this._$AH&&e!==I,s&&(this._$AH=e);else{const r=e;let o,a;for(e=n[0],o=0;o<n.length-1;o++)a=Z(this,r[i+o],t,o),a===I&&(a=this._$AH[o]),s||=!F(a)||a!==this._$AH[o],a===V?e=V:e!==V&&(e+=(a??"")+n[o+1]),this._$AH[o]=a}s&&!r&&this.j(e)}j(e){e===V?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}}class te extends ee{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===V?void 0:e}}class ie extends ee{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==V)}}class re extends ee{constructor(e,t,i,r,n){super(e,t,i,r,n),this.type=5}_$AI(e,t=this){if((e=Z(this,e,t,0)??V)===I)return;const i=this._$AH,r=e===V&&i!==V||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,n=e!==V&&(i===V||r);r&&this.element.removeEventListener(this.name,this,i),n&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}}class ne{constructor(e,t,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){Z(this,e)}}const se=A.litHtmlPolyfillSupport;se?.(Y,X),(A.litHtmlVersions??=[]).push("3.3.3");const oe=globalThis;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */class ae extends _{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){const t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=((e,t,i)=>{const r=i?.renderBefore??t;let n=r._$litPart$;if(void 0===n){const e=i?.renderBefore??null;r._$litPart$=n=new X(t.insertBefore(z(),e),e,void 0,i??{})}return n._$AI(e),n})(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return I}}ae._$litElement$=!0,ae.finalized=!0,oe.litElementHydrateSupport?.({LitElement:ae});const le=oe.litElementPolyfillSupport;le?.({LitElement:ae}),(oe.litElementVersions??=[]).push("4.2.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const ce=e=>(t,i)=>{void 0!==i?i.addInitializer(()=>{customElements.define(e,t)}):customElements.define(e,t)},ue={attribute:!0,type:String,converter:y,reflect:!1,hasChanged:x},de=(e=ue,t,i)=>{const{kind:r,metadata:n}=i;let s=globalThis.litPropertyMetadata.get(n);if(void 0===s&&globalThis.litPropertyMetadata.set(n,s=new Map),"setter"===r&&((e=Object.create(e)).wrapped=!0),s.set(i.name,e),"accessor"===r){const{name:r}=i;return{set(i){const n=t.get.call(this);t.set.call(this,i),this.requestUpdate(r,n,e,!0,i)},init(t){return void 0!==t&&this.C(r,void 0,e,t),t}}}if("setter"===r){const{name:r}=i;return function(i){const n=this[r];t.call(this,i),this.requestUpdate(r,n,e,!0,i)}}throw Error("Unsupported decorator location: "+r)};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function he(e){return(t,i)=>"object"==typeof i?de(e,t,i):((e,t,i)=>{const r=t.hasOwnProperty(i);return t.constructor.createProperty(i,e),r?Object.getOwnPropertyDescriptor(t,i):void 0})(e,t,i)}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function pe(e){return he({...e,state:!0,attribute:!1})}class me{constructor(e){this.hass=e}appeler(e,t={}){return this.hass.connection.sendMessagePromise({type:e,...t})}abonner(e){return this.hass.connection.subscribeMessage(e,{type:"home_stock/subscribe"})}appelerService(e,t,i={}){return this.hass.callService(e,t,i)}}function fe(e){return!!e&&"object"==typeof e&&"string"==typeof e.code&&"string"==typeof e.message}const ge=new Set(["not_loaded","invalid_field","invalid_value","not_found","already_exists","conversion_refused","shopping_refused"]);function ve(e){return ge.has(e.code)?e.message:"Une action a été refusée et n’a pas pu être envoyée."}const be="home_stock.file";class ye{constructor(e,t,i){this.stockage=e,this.envoyer=t,this.surRefus=i,this.actions=[],this.resultats=new Map;try{this.actions=JSON.parse(this.stockage.getItem(be)??"[]")}catch{this.actions=[]}}ajouter(e,t){const i={...t};return"string"!=typeof i.idempotency_key&&(i.idempotency_key=crypto.randomUUID()),this.actions.push({type:e,charge:i}),this.ecrire(),i.idempotency_key}taille(){return this.actions.length}async rejouer(){for(;this.actions.length;){const e=this.actions[0],t=e.charge.idempotency_key;try{await this.envoyer(e.type,e.charge)}catch(i){if(fe(i)){this.actions.shift(),this.ecrire(),t&&this.resultats.set(t,"refusee"),this.surRefus?.(e,ve(i));continue}return}this.actions.shift(),this.ecrire(),t&&this.resultats.set(t,"envoyee")}}resultatDe(e){const t=this.resultats.get(e);return this.resultats.delete(e),t}viderResultats(){this.resultats.clear()}ecrire(){this.stockage.setItem(be,JSON.stringify(this.actions))}}class xe{constructor(e){this.fenetre=e}disponible(){return Boolean(this.fenetre?.externalApp?.externalBus||this.fenetre?.webkit?.messageHandlers?.externalBus)}lire(){return new Promise(e=>{const t=this.fenetre.externalBus;let i=!1;const r=r=>{i||(i=!0,clearTimeout(n),this.fenetre.externalBus=t,e(r))},n=setTimeout(()=>r(null),6e4);this.fenetre.externalBus=e=>{const t="string"==typeof e?JSON.parse(e):e;return"bar_code/scan_result"===t.command?(this.envoyer({type:"bar_code/close"}),r(String(t.payload.rawValue))):"bar_code/aborted"!==t.command&&"bar_code/close"!==t.command||r(null),!0},this.envoyer({type:"bar_code/scan",payload:{title:"Scanner un article",description:"Visez le code-barres",alternative_option_label:"Saisir le code"}})})}envoyer(e){const t=JSON.stringify(e);this.fenetre.externalApp?.externalBus?this.fenetre.externalApp.externalBus(t):this.fenetre.webkit.messageHandlers.externalBus.postMessage(e)}}const $e=["ean_13","ean_8","upc_a","upc_e","code_128"];class _e{constructor(e){this.fenetre=e}disponible(){return Boolean(this.fenetre?.BarcodeDetector&&this.fenetre?.navigator?.mediaDevices)}async lire(){try{const e=new this.fenetre.BarcodeDetector({formats:$e});this.flux=await this.fenetre.navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}});const t=this.fenetre.document.createElement("video");t.srcObject=this.flux,t.setAttribute("playsinline","true"),t.setAttribute("muted","true"),t.style.cssText="position:fixed;inset:0;width:100%;height:100%;object-fit:cover;z-index:2147483647;background:#000;",this.fenetre.document.body.appendChild(t),this.video=t,await t.play();for(let i=0;i<300;i+=1){const i=await e.detect(t);if(i.length)return String(i[0].rawValue);await new Promise(e=>this.fenetre.requestAnimationFrame(e))}return null}finally{this.arreter()}}arreter(){this.flux?.getTracks().forEach(e=>e.stop()),this.flux=void 0,this.video?.remove(),this.video=void 0}}class Ae{disponible(){return!0}async lire(){return null}}const ke={label:"nom",brand:"marque",net_quantity:"poids net",image:"image",kcal_per_base_unit:"calories",proteins:"protéines",carbohydrates:"glucides",sugars:"sucres",added_sugars:"sucres ajoutés",fat:"matières grasses",saturated_fat:"graisses saturées",fiber:"fibres",salt:"sel",nutriscore:"Nutri-Score",nova:"classification NOVA",ecoscore:"Éco-score",allergens:"allergènes",traces:"traces",additives:"additifs",off_labels:"labels",off_raw:"réponse Open Food Facts"};function Ce(e,t,i){return null==e?"":"piece"===t?e.toFixed(2).replace(".",","):"g"===t||"ml"===t?null===i||i<=0?"":(e*i).toFixed(2).replace(".",","):""}function Ee(e,t,i){const r=Number.parseFloat(e.trim().replace(",","."));return Number.isFinite(r)?"piece"===t?r:"g"===t||"ml"===t?null===i||i<=0?null:r/i:null:null}function we(e){return e.known?e.article?.net_quantity??null:e.off?.net_quantity??null}function Pe(e){return e&&"object"==typeof e&&"message"in e&&"string"==typeof e.message?e.message:"Une erreur est survenue."}let Se=class extends ae{constructor(){super(...arguments),this.mode="rangement",this.productChoisi=null,this.nomNouveauProduit="",this.uniteNouveauProduit="piece",this.prixSaisi=null,this.poidsPaquet="",this.quantitePaquets=1,this.produitsBaseUnit={},this.rapportConversion=null,this.erreurConversion=null,this.erreurAction=null,this.erreurUnites=null,this.enCours=!1}willUpdate(e){if(e.has("resultat")&&this.resultat){this.productChoisi=this.resultat.preselected_product_id,this.nomNouveauProduit=this.resultat.off?.generic_name??"",this.uniteNouveauProduit=this.resultat.off?.net_unit??"piece";const e=we(this.resultat);this.poidsPaquet=null!==e?String(e):"",this.prixSaisi=null,this.quantitePaquets=1,this.rapportConversion=null,this.erreurConversion=null,this.erreurAction=null,this.erreurUnites=null,this.produitsBaseUnit={}}}updated(e){e.has("resultat")&&this.resultat&&!this.resultat.known&&this.resultat.candidates.length&&this.connexion&&this.chargerUnitesProduits()}async chargerUnitesProduits(){this.erreurUnites=null;try{const e=await this.connexion.appeler("home_stock/products/list"),t={};for(const i of e.products)t[i.id]=i.base_unit;this.produitsBaseUnit=t}catch{this.erreurUnites="Impossible de récupérer les informations du produit. Vérifiez la connexion."}}uniteConnue(){return this.resultat.known?this.resultat.product?.base_unit??null:"new"===this.productChoisi?this.uniteNouveauProduit:"number"==typeof this.productChoisi?this.produitsBaseUnit[this.productChoisi]??null:null}get poidsEffectif(){return function(e){const t=Number.parseFloat(e.trim().replace(",","."));return Number.isFinite(t)&&t>0?t:null}(this.poidsPaquet)}get valeurPrix(){if(null!==this.prixSaisi)return this.prixSaisi;const e=this.uniteConnue(),t="piece"===e?null:this.poidsEffectif;return Ce(this.resultat.price?.price_per_base_unit,e,t)}get raisonBlocage(){if(!this.resultat)return null;if(!this.resultat.known){if(!this.connexion)return"Connexion indisponible.";if(null===this.productChoisi)return"Choisissez un produit.";if("new"===this.productChoisi&&!this.nomNouveauProduit.trim())return"Donnez un nom au nouveau produit."}const e=this.uniteConnue();return null===e?this.erreurUnites??"Chargement des informations du produit…":"g"!==e&&"ml"!==e||null!==this.poidsEffectif?null:"Indiquez le poids du paquet pour calculer le prix."}get peutValider(){return!this.enCours&&null===this.raisonBlocage}enregistrerPoidsCorrige(e,t){const i={article_id:e,fields:{net_quantity:t}};this.file?this.file.ajouter("home_stock/article/update",i):this.connexion&&this.connexion.appeler("home_stock/article/update",i).catch(()=>{})}async valider(){if(this.peutValider){this.enCours=!0,this.erreurAction=null;try{const e=this.uniteConnue(),t="piece"===e?null:this.poidsEffectif,i=null===we(this.resultat);let r,n=[];if(this.resultat.known)r=this.resultat.article.id,null!==t&&i&&this.enregistrerPoidsCorrige(r,t);else{const e={code:this.resultat.code};this.resultat.off_raw&&(e.off=this.resultat.off_raw),this.resultat.off_source&&(e.off_source=this.resultat.off_source),"new"===this.productChoisi?e.new_product={name:this.nomNouveauProduit.trim(),base_unit:this.uniteNouveauProduit}:e.product_id=this.productChoisi,null!==t&&i&&(e.fields={net_quantity:t});const s=await this.connexion.appeler("home_stock/article/create",e);r=s.article_id,n=s.off_dropped_fields??[]}const s={articleId:r,quantite:"piece"===e?this.quantitePaquets:t*this.quantitePaquets,prixUnitaire:Ee(this.valeurPrix,e,t),mode:this.mode,offDroppedFields:n};this.dispatchEvent(new CustomEvent("article-pret",{detail:s,bubbles:!0,composed:!0}))}catch(e){this.erreurAction=Pe(e)}finally{this.enCours=!1}}}async voirEffetConversion(){const e=this.resultat.conversion_offer;if(e&&this.connexion){this.erreurConversion=null;try{this.rapportConversion=await this.connexion.appeler("home_stock/product/convert_unit",{product_id:e.product_id,to_unit:e.to_unit,reference_quantity:e.reference_quantity,dry_run:!0})}catch(e){this.erreurConversion=Pe(e)}}}async appliquerConversion(){const e=this.resultat.conversion_offer;if(e&&this.connexion&&this.rapportConversion){this.erreurConversion=null;try{this.rapportConversion=await this.connexion.appeler("home_stock/product/convert_unit",{product_id:e.product_id,to_unit:e.to_unit,reference_quantity:e.reference_quantity,dry_run:!1})}catch(e){this.erreurConversion=Pe(e)}}}rendreRattachement(){return this.resultat.known?V:H`
      <section class="rattachement">
        ${this.resultat.candidates.map(e=>H`
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
        ${"new"===this.productChoisi?H`
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
        ${this.erreurUnites?H`
          <p class="erreur-unite">${this.erreurUnites}</p>
          <button class="reessayer-unite" @click=${()=>{this.chargerUnitesProduits()}}>
            Réessayer
          </button>`:V}
      </section>
    `}rendreAlerteOff(){const e=this.resultat;return e.known||e.off?V:e.throttled?H`<p class="alerte-off">Open Food Facts limite les requêtes en ce moment — réessayez
        dans un instant plutôt que de créer un doublon.</p>`:e.timed_out?H`<p class="alerte-off">Open Food Facts n'a pas répondu à temps — le produit existe
        peut-être déjà là-bas, réessayez avant de créer un doublon.</p>`:V}rendreConversion(){const e=this.resultat.conversion_offer;return e?H`
      <section class="conversion-offre">
        <p>Passer de pièce à ${e.to_unit} — 1 unité = ${e.reference_quantity} ${e.to_unit}</p>
        ${this.rapportConversion?H`
          <p class="rapport-conversion">
            ${this.rapportConversion.articles} article(s), ${this.rapportConversion.batches} lot(s),
            ${this.rapportConversion.movements} mouvement(s) concernés
            ${this.rapportConversion.articles_using_reference.length?H`
              — dont ${this.rapportConversion.articles_using_reference.length} article(s) qui seront
              re-pesé(s) avec un poids de référence estimé, faute de poids propre.`:"."}
          </p>
          ${this.rapportConversion.applied?H`<p class="conversion-appliquee">Conversion appliquée.</p>`:H`<button class="appliquer-conversion" @click=${this.appliquerConversion}>
                Appliquer la conversion
              </button>`}
        `:H`<button class="voir-effet" @click=${this.voirEffetConversion}>
            Voir l'effet du changement d'unité
          </button>`}
        ${this.erreurConversion?H`<p class="erreur-conversion">${this.erreurConversion}</p>`:V}
      </section>
    `:V}render(){if(!this.resultat)return V;const e=this.resultat,t=e.off?.label??e.article?.label??e.product?.name??"Article",i=e.off?.brand??e.article?.brand??null,r=e.article?.net_quantity??e.off?.net_quantity??null,n=e.product?.base_unit??e.off?.net_unit??"",s=e.off?.image??e.article?.image??null,o=e.off?.nutriscore??e.article?.nutriscore??null,a=function(e){const t=e.off?.nutrition_per_100?.kcal;if(null!=t)return t;const i=e.article?.kcal_per_base_unit,r=e.product?.base_unit;return null==i||"g"!==r&&"ml"!==r?null:100*i}(e),l=this.uniteConnue(),c="piece"===l?null:this.poidsEffectif,u="g"===l||"ml"===l?Ee(this.valeurPrix,l,c):null,d=null!=u?1e3*u:null,h="ml"===l?"L":"kg";return H`
      <section class="entete">
        ${s?H`<img class="image" src=${s} alt="" />`:V}
        <h2 class="nom">${t}</h2>
        ${i?H`<p class="marque">${i}</p>`:V}
        ${r?H`<p class="poids">${r} ${n}</p>`:V}
        ${o?H`<p class="nutriscore">Nutri-Score ${o.toUpperCase()}</p>`:V}
        ${null!=a?H`<p class="kcal">${Math.round(a)} kcal / 100 g</p>`:V}
      </section>

      ${this.rendreAlerteOff()}
      ${this.rendreRattachement()}

      <section class="prix">
        <p class="prix-provenance">${p=e.price,p&&null!=p.price_per_base_unit&&p.source?"store"===p.source?p.store?`dernier prix ${p.store}`:"dernier prix en magasin":"open_prices"===p.source?"Open Prices":"dernier prix connu":"Aucun prix connu"}</p>
        ${"g"!==l&&"ml"!==l||null!==we(e)?V:H`
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
        ${null!=d?H`
          <p class="prix-detail">soit ${d.toFixed(2).replace(".",",")} €/${h}</p>
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

      ${this.raisonBlocage?H`<p class="motif-blocage">${this.raisonBlocage}</p>`:V}
      ${this.erreurAction?H`<p class="erreur-action">${this.erreurAction}</p>`:V}

      <button class="action-principale" ?disabled=${!this.peutValider} @click=${this.valider}>
        ${"panier"===this.mode?"Au panier":"Ranger"}
      </button>
    `;var p}};Se.styles=o`
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
    button.voir-effet, button.appliquer-conversion {
      min-height: 48px; width: 100%; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
  `,e([he({attribute:!1})],Se.prototype,"resultat",void 0),e([he({attribute:!1})],Se.prototype,"mode",void 0),e([he({attribute:!1})],Se.prototype,"connexion",void 0),e([he({attribute:!1})],Se.prototype,"file",void 0),e([pe()],Se.prototype,"productChoisi",void 0),e([pe()],Se.prototype,"nomNouveauProduit",void 0),e([pe()],Se.prototype,"uniteNouveauProduit",void 0),e([pe()],Se.prototype,"prixSaisi",void 0),e([pe()],Se.prototype,"poidsPaquet",void 0),e([pe()],Se.prototype,"quantitePaquets",void 0),e([pe()],Se.prototype,"produitsBaseUnit",void 0),e([pe()],Se.prototype,"rapportConversion",void 0),e([pe()],Se.prototype,"erreurConversion",void 0),e([pe()],Se.prototype,"erreurAction",void 0),e([pe()],Se.prototype,"erreurUnites",void 0),e([pe()],Se.prototype,"enCours",void 0),Se=e([ce("home-stock-fiche")],Se);let qe=class extends ae{constructor(){super(...arguments),this.fenetre=window,this.derniereFiche=null,this.session=null,this.enAttente=0,this.saisieOuverte=!1,this.codeSaisi="",this.enCours=!1,this.erreur=null}obtenirScanner(){return this.scanner||(this.scanner=function(e){const t=new xe(e);if(t.disponible())return t;const i=new _e(e);return i.disponible()?i:new Ae}(this.fenetre??window)),this.scanner}async lancerScan(){const e=this.obtenirScanner();if("ScannerClavier"!==e.constructor.name){this.enCours=!0,this.erreur=null;try{const t=await e.lire();t&&this.emettreCode(t)}catch{this.erreur="La caméra n’a pas pu être utilisée. Essayez la saisie manuelle."}finally{this.enCours=!1}}else this.saisieOuverte=!0}emettreCode(e){this.saisieOuverte=!1,this.codeSaisi="",this.dispatchEvent(new CustomEvent("code-lu",{detail:{code:e},bubbles:!0,composed:!0}))}validerSaisie(){const e=this.codeSaisi.trim();e&&this.emettreCode(e)}render(){return H`
      ${this.session?H`
        <p class="session-banniere">
          Session ouverte${this.session.store?` — ${this.session.store}`:""}
        </p>`:V}

      <button class="bouton-scan" ?disabled=${this.enCours} @click=${this.lancerScan}>
        ${this.enCours?"Scan en cours…":"Scanner un article"}
      </button>

      ${this.erreur?H`<p class="erreur">${this.erreur}</p>`:V}

      ${this.derniereFiche?H`
        <section class="derniere-fiche">
          ${this.derniereFiche.image?H`<img src=${this.derniereFiche.image} alt="" />`:V}
          <p class="derniere-fiche-nom">
            ${this.derniereFiche.nom}${this.derniereFiche.marque?` — ${this.derniereFiche.marque}`:""}
          </p>
          <p class="derniere-fiche-statut">${this.derniereFiche.statut}</p>
          ${void 0!==this.derniereFiche.quantite?H`
            <p class="derniere-fiche-quantite">
              Quantité : ${this.derniereFiche.quantite}${null!=this.derniereFiche.prixTotal?` — ${this.derniereFiche.prixTotal.toFixed(2).replace(".",",")} €`:""}
            </p>`:V}
          ${this.derniereFiche.ignores?.length?H`
            <p class="derniere-fiche-ignores">
              Ignoré par Open Food Facts : ${e=this.derniereFiche.ignores,e.map(e=>ke[e]??e).join(", ")}
            </p>`:V}
        </section>`:V}

      ${this.enAttente>0?H`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:V}

      <button class="bouton-saisie" @click=${()=>{this.saisieOuverte=!this.saisieOuverte}}>
        Saisir le code
      </button>

      ${this.saisieOuverte?H`
        <div class="saisie-manuelle">
          <input class="champ-code" inputmode="numeric" placeholder="Code-barres" .value=${this.codeSaisi}
            @input=${e=>{this.codeSaisi=e.target.value}}
            @keydown=${e=>{"Enter"===e.key&&this.validerSaisie()}} />
          <button class="valider-saisie" @click=${this.validerSaisie}>Valider</button>
        </div>`:V}
    `;var e}};qe.styles=o`
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
  `,e([he({attribute:!1})],qe.prototype,"fenetre",void 0),e([he({attribute:!1})],qe.prototype,"derniereFiche",void 0),e([he({attribute:!1})],qe.prototype,"session",void 0),e([he({attribute:!1})],qe.prototype,"enAttente",void 0),e([pe()],qe.prototype,"saisieOuverte",void 0),e([pe()],qe.prototype,"codeSaisi",void 0),e([pe()],qe.prototype,"enCours",void 0),e([pe()],qe.prototype,"erreur",void 0),qe=e([ce("home-stock-scanner")],qe);let Re=class extends ae{constructor(){super(...arguments),this.donnees=null,this.enAttente=0,this.ligneArmee=null,this.prixSaisiParLigne={},this.erreurPrixParLigne={},this.deltaParLigne={},this.quantiteVueParLigne={}}willUpdate(e){if(e.has("donnees")){this.ligneArmee=null;for(const e of this.donnees?.lines??[])if(this.quantiteVueParLigne[e.id]!==e.quantity&&(this.quantiteVueParLigne[e.id]=e.quantity,this.deltaParLigne[e.id])){const{[e.id]:t,...i}=this.deltaParLigne;this.deltaParLigne=i}}}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>(this.avertirFile(),"envoyee"===this.file.resultatDe(i)))}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}quantiteAffichee(e){return e.quantity+(this.deltaParLigne[e.id]??0)}ajusterQuantite(e,t){this.ligneArmee=null;const i=(this.deltaParLigne[e.id]??0)+t,r=e.quantity+i;r<=0||(this.deltaParLigne={...this.deltaParLigne,[e.id]:i},this.ecrire("home_stock/session/update_line",{line_id:e.id,quantity:r}))}saisirPrix(e,t){this.ligneArmee=null,this.prixSaisiParLigne={...this.prixSaisiParLigne,[e.id]:t}}validerPrix(e){this.ligneArmee=null;const t=this.prixSaisiParLigne[e.id];if(void 0===t)return;const i=Ee(t,e.base_unit,e.net_quantity);if(null===i)return void(this.erreurPrixParLigne={...this.erreurPrixParLigne,[e.id]:"Prix non enregistré : poids du paquet inconnu."});if(this.erreurPrixParLigne[e.id]){const{[e.id]:t,...i}=this.erreurPrixParLigne;this.erreurPrixParLigne=i}this.ecrire("home_stock/session/update_line",{line_id:e.id,unit_price:i});const{[e.id]:r,...n}=this.prixSaisiParLigne;this.prixSaisiParLigne=n}supprimer(e){this.ecrire("home_stock/session/remove_line",{line_id:e.id}),this.ligneArmee=null}passerEnCaisse(){this.ligneArmee=null,this.ecrire("home_stock/session/checkout",{})}valeurPrix(e){const t=this.prixSaisiParLigne[e.id];return void 0!==t?t:Ce(e.unit_price,e.base_unit,e.net_quantity)}rendreLigne(e){const t=function(e){return"piece"===e.base_unit?1:e.net_quantity&&e.net_quantity>0?e.net_quantity:1}(e),i=this.quantiteAffichee(e),r=e.article_label??e.product_name;return H`
      <article class="ligne">
        ${e.image?H`<img class="image" src=${e.image} alt="" />`:V}
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
          ${this.erreurPrixParLigne[e.id]?H`
            <p class="erreur-prix">${this.erreurPrixParLigne[e.id]}</p>
          `:V}
        </div>
        ${this.ligneArmee===e.id?H`
          <div class="confirmation-suppression">
            <button class="confirmer-suppression" @click=${()=>this.supprimer(e)}>Confirmer</button>
            <button class="annuler-suppression" @click=${()=>{this.ligneArmee=null}}>Annuler</button>
          </div>
        `:H`
          <button class="supprimer" aria-label="Retirer du panier" @click=${()=>{this.ligneArmee=e.id}}>
            ×
          </button>
        `}
      </article>
    `}render(){const e=this.donnees;if(!e)return H`<p class="vide">Aucune session de courses ouverte.</p>`;const t=function(e){const t=[];for(const i of e){const e=i.aisle_name??"Sans rayon",r=t[t.length-1];r&&r.rayon===e?r.lignes.push(i):t.push({rayon:e,lignes:[i]})}return t}(e.lines),i="shopping"!==e.session.state;return H`
      <section class="entete">
        <p class="magasin">${e.session.store??"Sans enseigne"}</p>
        <p class="total">${r=e.totals.total,`${r.toFixed(2).replace(".",",")} €`}</p>
      </section>

      ${this.enAttente>0?H`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:V}

      ${0===e.lines.length?H`<p class="vide">Le panier est vide.</p>`:V}

      ${t.map(e=>H`
        <section class="rayon">
          <h3 class="rayon-nom">${e.rayon}</h3>
          ${e.lignes.map(e=>this.rendreLigne(e))}
        </section>
      `)}

      <button class="checkout" ?disabled=${0===e.totals.lines||i} @click=${this.passerEnCaisse}>
        ${i?"Déjà en caisse":"Passage en caisse"}
      </button>
    `;var r}};function ze(e,t){const i=new Date(t.getFullYear(),t.getMonth(),t.getDate()+e);return`${String(i.getFullYear()).padStart(4,"0")}-${String(i.getMonth()+1).padStart(2,"0")}-${String(i.getDate()).padStart(2,"0")}`}Re.styles=o`
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
  `,e([he({attribute:!1})],Re.prototype,"donnees",void 0),e([he({attribute:!1})],Re.prototype,"connexion",void 0),e([he({attribute:!1})],Re.prototype,"file",void 0),e([he({attribute:!1})],Re.prototype,"enAttente",void 0),e([pe()],Re.prototype,"ligneArmee",void 0),e([pe()],Re.prototype,"prixSaisiParLigne",void 0),e([pe()],Re.prototype,"erreurPrixParLigne",void 0),e([pe()],Re.prototype,"deltaParLigne",void 0),Re=e([ce("home-stock-panier")],Re);let Fe=class extends ae{constructor(){super(...arguments),this.lignes=[],this.enAttente=0,this.emplacements=[],this.erreurEmplacements=null,this.emplacementChoisi={},this.enCours=new Set,this.aEuDesLignes=!1,this.termineEnvoye=!1}connectedCallback(){super.connectedCallback(),this.chargerEmplacements()}willUpdate(e){e.has("lignes")&&this.lignes.length>0&&(this.aEuDesLignes=!0)}updated(){this.aEuDesLignes&&0===this.lignes.length&&!this.termineEnvoye&&(this.termineEnvoye=!0,this.dispatchEvent(new CustomEvent("termine",{bubbles:!0,composed:!0})))}async chargerEmplacements(){if(this.connexion){this.erreurEmplacements=null;try{const e=await this.connexion.appeler("home_stock/locations/list");this.emplacements=e.locations}catch{this.erreurEmplacements="Impossible de récupérer les emplacements. Vérifiez la connexion."}}}emplacementPour(e){const t=this.emplacementChoisi[String(e.id)];return void 0!==t?t:e.default_location_id}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>(this.avertirFile(),"envoyee"===this.file.resultatDe(i)))}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}ranger(e,t){const i=this.emplacementPour(e);if(null===i)return;const r=String(e.id);if(this.enCours.has(r))return;this.enCours=new Set(this.enCours).add(r);const n=()=>{const e=new Set(this.enCours);e.delete(r),this.enCours=e};"session"===e.source?this.ecrire("home_stock/session/store_line",{line_id:e.id,location_id:i,best_before:t.date}).then(n):this.ecrire("home_stock/stock/add",{article_id:e.article_id,quantity:e.quantity,location_id:i,best_before:t.date,price_per_base_unit:e.unit_price}).then(t=>{n(),t&&this.dispatchEvent(new CustomEvent("ligne-autonome-rangee",{detail:{id:e.id},bubbles:!0,composed:!0}))})}rendreLigne(e){const t=String(e.id),i=this.enCours.has(t),r=this.emplacementPour(e),n=function(e,t){const i=[];t&&t>0&&i.push({libelle:`+${t} j (habituel)`,date:ze(t,e)}),i.push({libelle:"+3 j",date:ze(3,e)},{libelle:"+1 sem",date:ze(7,e)},{libelle:"+1 mois",date:ze(31,e)});const r=new Set,n=i.filter(e=>e.date&&!r.has(e.date)&&r.add(e.date));return[...n,{libelle:"Sans DLC",date:null}]}(new Date,e.default_shelf_life_days);return H`
      <article class="ligne">
        ${e.image?H`<img class="image" src=${e.image} alt="" />`:V}
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
              ${null===r?H`
                <option value="" disabled selected>Choisir…</option>
              `:V}
              ${this.emplacements.map(e=>H`
                <option value=${String(e.id)} ?selected=${e.id===r}>${e.name}</option>
              `)}
            </select>
          </label>
          ${null===r?H`
            <p class="emplacement-manquant">Choisissez un emplacement avant de ranger.</p>
          `:V}
          ${this.erreurEmplacements?H`<p class="erreur">${this.erreurEmplacements}</p>`:V}
          <div class="raccourcis-dlc">
            ${n.map(t=>H`
              <button class="raccourci-dlc" ?disabled=${i||null===r}
                @click=${()=>this.ranger(e,t)}>
                ${i?"Rangement…":t.libelle}
              </button>
            `)}
          </div>
        </div>
      </article>
    `}render(){if(0===this.lignes.length)return H`<p class="tout-range">Tout est rangé.</p>`;const e=function(e,t,i=e=>e.default_location_id){const r=e=>null===e?"Emplacement à choisir":t.find(t=>t.id===e)?.name??"Emplacement à choisir",n=[];for(const t of e){const e=i(t);let s=n.find(t=>t.emplacementId===e);s||(s={emplacementId:e,nom:r(e),lignes:[]},n.push(s)),s.lignes.push(t)}return n}(this.lignes,this.emplacements,e=>this.emplacementPour(e));return H`
      ${this.enAttente>0?H`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:V}
      ${e.map(e=>H`
        <section class="emplacement">
          <h3 class="emplacement-nom">${e.nom}</h3>
          ${e.lignes.map(e=>this.rendreLigne(e))}
        </section>
      `)}
    `}};function Ue(e){return{name:e.name,aisle_id:null!==e.aisle_id?String(e.aisle_id):"",category_id:null!==e.category_id?String(e.category_id):"",default_location_id:null!==e.default_location_id?String(e.default_location_id):"",min_quantity:null!==e.min_quantity?String(e.min_quantity):"",default_shelf_life_days:null!==e.default_shelf_life_days?String(e.default_shelf_life_days):""}}function Ne(e){const t=e.trim();return""===t?null:Number(t)}Fe.styles=o`
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
  `,e([he({attribute:!1})],Fe.prototype,"lignes",void 0),e([he({attribute:!1})],Fe.prototype,"connexion",void 0),e([he({attribute:!1})],Fe.prototype,"file",void 0),e([he({attribute:!1})],Fe.prototype,"enAttente",void 0),e([pe()],Fe.prototype,"emplacements",void 0),e([pe()],Fe.prototype,"erreurEmplacements",void 0),e([pe()],Fe.prototype,"emplacementChoisi",void 0),e([pe()],Fe.prototype,"enCours",void 0),Fe=e([ce("home-stock-rangement")],Fe);let Oe=class extends ae{constructor(){super(...arguments),this.enAttente=0,this.produits=[],this.rayons=[],this.emplacements=[],this.quantitesParProduit={},this.erreurChargement=null,this.recherche="",this.produitEditeId=null,this.produitEnEdition=null,this.brouillon=null,this.erreurEdition=null,this.enCours=!1,this.enAttenteEnvoi=!1,this.nomRayon=e=>null===e?"Sans rayon":this.rayons.find(t=>t.id===e)?.name??"Sans rayon"}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(this.connexion){this.erreurChargement=null;try{const[e,t,i,r]=await Promise.all([this.connexion.appeler("home_stock/products/list"),this.connexion.appeler("home_stock/aisles/list"),this.connexion.appeler("home_stock/locations/list"),this.connexion.appeler("home_stock/batches/list")]);this.produits=e.products,this.rayons=t.aisles,this.emplacements=i.locations;const n={};for(const e of r.batches)n[e.product_id]=(n[e.product_id]??0)+e.remaining;this.quantitesParProduit=n}catch{this.erreurChargement="Impossible de récupérer le catalogue. Vérifiez la connexion."}}}nomEmplacement(e){return null===e?"Aucun":this.emplacements.find(t=>t.id===e)?.name??"Aucun"}get produitsFiltres(){return function(e,t,i){const r=t.trim().toLowerCase();return r?e.filter(e=>e.name.toLowerCase().includes(r)||i(e.aisle_id).toLowerCase().includes(r)):e}(this.produits,this.recherche,this.nomRayon)}async ouvrirEdition(e){if(this.produitEditeId=e.id,this.produitEnEdition=e,this.brouillon=Ue(e),this.erreurEdition=null,this.enAttenteEnvoi=!1,this.connexion)try{const t=await this.connexion.appeler("home_stock/product/get",{product_id:e.id});this.produitEditeId===e.id&&(this.produitEnEdition=t.product,this.brouillon=Ue(t.product))}catch{}}fermerEdition(){this.produitEditeId=null,this.produitEnEdition=null,this.brouillon=null,this.erreurEdition=null,this.enAttenteEnvoi=!1}modifierBrouillon(e,t){this.brouillon&&(this.brouillon={...this.brouillon,[e]:t})}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>(this.avertirFile(),"envoyee"===this.file.resultatDe(i)))}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}async enregistrer(){const e=this.produitEnEdition,t=this.brouillon;if(!e||!t||this.enCours)return;const i=function(e,t){const i={},r=e.name.trim();return r&&r!==t.name&&(i.name=r),Ne(e.aisle_id)!==t.aisle_id&&(i.aisle_id=Ne(e.aisle_id)),Ne(e.category_id)!==t.category_id&&(i.category_id=Ne(e.category_id)),Ne(e.default_location_id)!==t.default_location_id&&(i.default_location_id=Ne(e.default_location_id)),Ne(e.min_quantity)!==t.min_quantity&&(i.min_quantity=Ne(e.min_quantity)),Ne(e.default_shelf_life_days)!==t.default_shelf_life_days&&(i.default_shelf_life_days=Ne(e.default_shelf_life_days)),i}(t,e);if(0===Object.keys(i).length)return void this.fermerEdition();this.enCours=!0,this.erreurEdition=null,this.enAttenteEnvoi=!1;const r=await this.ecrire("home_stock/product/update",{product_id:e.id,fields:i});this.enCours=!1,r?(await this.charger(),this.fermerEdition()):this.enAttenteEnvoi=!0}rendreEdition(e){const t=this.brouillon;return t?H`
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
            ${this.rayons.map(e=>H`<option value=${String(e.id)}>${e.name}</option>`)}
          </select>
        </label>
        <label class="champ">
          Catégorie (identifiant)
          <input class="champ-categorie" inputmode="numeric" placeholder="ex. 3" .value=${t.category_id}
            @input=${e=>this.modifierBrouillon("category_id",e.target.value)} />
          <span class="aide">Aucune liste de noms de catégorie n'est disponible côté serveur.</span>
        </label>
        <label class="champ">
          Emplacement par défaut
          <select class="champ-emplacement" .value=${t.default_location_id}
            @change=${e=>this.modifierBrouillon("default_location_id",e.target.value)}>
            <option value="">Aucun</option>
            ${this.emplacements.map(e=>H`<option value=${String(e.id)}>${e.name}</option>`)}
          </select>
        </label>
        <label class="champ">
          Seuil de réapprovisionnement${"piece"!==e.base_unit?` (${e.base_unit})`:""}
          <input class="champ-seuil" inputmode="decimal" placeholder="ex. 200" .value=${t.min_quantity}
            @input=${e=>this.modifierBrouillon("min_quantity",e.target.value)} />
        </label>
        <label class="champ">
          Durée de conservation (jours)
          <input class="champ-conservation" inputmode="numeric" placeholder="ex. 5" .value=${t.default_shelf_life_days}
            @input=${e=>this.modifierBrouillon("default_shelf_life_days",e.target.value)} />
        </label>
        <p class="champ-lecture-seule">
          Unité de base : ${"piece"===e.base_unit?"à la pièce":e.base_unit}
          — se change uniquement par une conversion, pas depuis cet écran.
        </p>
        ${this.enAttenteEnvoi?H`
          <p class="etat-envoi">Enregistrement en file d'attente (hors ligne) ou refusé — voir le message ci-dessus.</p>
        `:V}
        ${this.erreurEdition?H`<p class="erreur">${this.erreurEdition}</p>`:V}
        <div class="actions-edition">
          <button class="enregistrer" ?disabled=${this.enCours} @click=${this.enregistrer}>
            ${this.enCours?"Enregistrement…":"Enregistrer"}
          </button>
          <button class="annuler" ?disabled=${this.enCours} @click=${()=>this.fermerEdition()}>Annuler</button>
        </div>
      </div>
    `:V}rendreLigne(e){const t=this.quantitesParProduit[e.id]??0,i="piece"!==e.base_unit?` ${e.base_unit}`:"";return H`
      <article class="ligne">
        <div class="infos">
          <p class="nom">${e.name}</p>
          <p class="meta">
            ${this.nomRayon(e.aisle_id)} · en stock : ${t}${i}
            ${null!==e.min_quantity?H` · seuil : ${e.min_quantity}${i}`:V}
            · emplacement : ${this.nomEmplacement(e.default_location_id)}
          </p>
        </div>
        <button class="modifier" @click=${()=>this.ouvrirEdition(e)}>Modifier</button>
        ${this.produitEditeId===e.id?this.rendreEdition(this.produitEnEdition??e):V}
      </article>
    `}render(){return H`
      <input class="recherche" type="search" placeholder="Rechercher un produit ou un rayon…"
        .value=${this.recherche}
        @input=${e=>{this.recherche=e.target.value}} />

      ${this.enAttente>0?H`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:V}

      ${this.erreurChargement?H`
        <p class="erreur">${this.erreurChargement}</p>
        <button class="reessayer" @click=${()=>{this.charger()}}>Réessayer</button>
      `:V}

      ${this.erreurChargement||0!==this.produitsFiltres.length?V:H`
        <p class="vide">Aucun produit.</p>
      `}

      <div class="liste">
        ${this.produitsFiltres.map(e=>this.rendreLigne(e))}
      </div>
    `}};Oe.styles=o`
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
    .edition {
      flex: 1 0 100%; display: flex; flex-direction: column; gap: 8px; margin-top: 8px;
      padding: 12px; border-radius: 8px; background: var(--secondary-background-color);
      box-sizing: border-box;
    }
    .champ { display: block; font-size: 0.85rem; }
    .champ-nom, .champ-rayon, .champ-categorie, .champ-emplacement, .champ-seuil, .champ-conservation {
      display: block; width: 100%; min-height: 48px; box-sizing: border-box; font-size: 1rem;
      padding: 4px 8px; margin-top: 4px;
    }
    .aide { display: block; color: var(--secondary-text-color); font-size: 0.75rem; margin-top: 2px; }
    .champ-lecture-seule { color: var(--secondary-text-color); font-size: 0.85rem; margin: 4px 0; }
    .etat-envoi { color: var(--secondary-text-color); font-size: 0.85rem; }
    .actions-edition { display: flex; flex-wrap: wrap; gap: 8px; }
    .enregistrer, .annuler {
      min-height: 48px; flex: 1; border-radius: 8px; border: none; font-size: 0.95rem;
    }
    .enregistrer { background: var(--primary-color); color: var(--text-primary-color, #fff); }
    .enregistrer:disabled { opacity: 0.5; }
    .annuler { background: var(--secondary-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color, #ddd); }
  `,e([he({attribute:!1})],Oe.prototype,"connexion",void 0),e([he({attribute:!1})],Oe.prototype,"file",void 0),e([he({attribute:!1})],Oe.prototype,"enAttente",void 0),e([pe()],Oe.prototype,"produits",void 0),e([pe()],Oe.prototype,"rayons",void 0),e([pe()],Oe.prototype,"emplacements",void 0),e([pe()],Oe.prototype,"quantitesParProduit",void 0),e([pe()],Oe.prototype,"erreurChargement",void 0),e([pe()],Oe.prototype,"recherche",void 0),e([pe()],Oe.prototype,"produitEditeId",void 0),e([pe()],Oe.prototype,"produitEnEdition",void 0),e([pe()],Oe.prototype,"brouillon",void 0),e([pe()],Oe.prototype,"erreurEdition",void 0),e([pe()],Oe.prototype,"enCours",void 0),e([pe()],Oe.prototype,"enAttenteEnvoi",void 0),Oe=e([ce("home-stock-catalogue")],Oe);let Le=class extends ae{constructor(){super(...arguments),this.enAttente=0,this.rayons=[],this.emplacements=[],this.erreurChargement=null,this.resyncEnCours=!1,this.messageResync=null,this.erreurResync=null}connectedCallback(){super.connectedCallback(),this.charger()}async charger(){if(this.connexion){this.erreurChargement=null;try{const[e,t]=await Promise.all([this.connexion.appeler("home_stock/aisles/list"),this.connexion.appeler("home_stock/locations/list")]);this.rayons=e.aisles,this.emplacements=t.locations}catch{this.erreurChargement="Impossible de récupérer les rayons et les emplacements. Vérifiez la connexion."}}}ecrire(e,t){if(!this.file)return Promise.resolve(!1);const i=this.file.ajouter(e,t);return this.avertirFile(),this.file.rejouer().then(()=>(this.avertirFile(),"envoyee"===this.file.resultatDe(i)))}avertirFile(){this.dispatchEvent(new CustomEvent("file-changee",{bubbles:!0,composed:!0}))}deplacerRayon(e,t){const i=function(e,t,i){const r=t+i;if(r<0||r>=e.length)return null;const n=[...e];return[n[t],n[r]]=[n[r],n[t]],n}(this.rayons,e,t);null!==i&&(this.rayons=i,this.ecrire("home_stock/aisles/reorder",{aisle_ids:i.map(e=>e.id)}))}async resynchroniser(){if(this.connexion&&!this.resyncEnCours){this.resyncEnCours=!0,this.messageResync=null,this.erreurResync=null;try{await this.connexion.appelerService("home_stock","resync_off",{all:!0}),this.messageResync="Resynchronisation lancée en tâche de fond — environ 40 minutes pour tout le catalogue. Les champs corrigés à la main ne sont jamais écrasés."}catch(e){this.erreurResync=function(e){return e&&"object"==typeof e&&"message"in e&&"string"==typeof e.message?e.message:"Une erreur est survenue."}(e)}finally{this.resyncEnCours=!1}}}rendreRayons(){return 0===this.rayons.length?H`<p class="vide">Aucun rayon.</p>`:H`
      <ul class="liste-rayons">
        ${this.rayons.map((e,t)=>H`
          <li class="rayon">
            <span class="rayon-nom">${e.name}</span>
            <span class="rayon-boutons">
              <button class="monter" aria-label="Monter ${e.name}" ?disabled=${0===t}
                @click=${()=>this.deplacerRayon(t,-1)}>▲</button>
              <button class="descendre" aria-label="Descendre ${e.name}"
                ?disabled=${t===this.rayons.length-1}
                @click=${()=>this.deplacerRayon(t,1)}>▼</button>
            </span>
          </li>
        `)}
      </ul>
    `}rendreEmplacements(){return 0===this.emplacements.length?H`<p class="vide">Aucun emplacement.</p>`:H`
      <ul class="liste-emplacements">
        ${this.emplacements.map(e=>H`
          <li class="emplacement">
            <span class="emplacement-nom">${e.name}</span>
            <span class="emplacement-type">${e.kind}</span>
          </li>
        `)}
      </ul>
    `}render(){return H`
      ${this.enAttente>0?H`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:V}

      ${this.erreurChargement?H`
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
        ${this.messageResync?H`<p class="message-resync">${this.messageResync}</p>`:V}
        ${this.erreurResync?H`<p class="erreur">${this.erreurResync}</p>`:V}
      </section>
    `}};Le.styles=o`
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
  `,e([he({attribute:!1})],Le.prototype,"connexion",void 0),e([he({attribute:!1})],Le.prototype,"file",void 0),e([he({attribute:!1})],Le.prototype,"enAttente",void 0),e([pe()],Le.prototype,"rayons",void 0),e([pe()],Le.prototype,"emplacements",void 0),e([pe()],Le.prototype,"erreurChargement",void 0),e([pe()],Le.prototype,"resyncEnCours",void 0),e([pe()],Le.prototype,"messageResync",void 0),e([pe()],Le.prototype,"erreurResync",void 0),Le=e([ce("home-stock-reglages")],Le);let je=class extends ae{constructor(){super(...arguments),this.narrow=!1,this.ecran="scanner",this.enAttente=0,this.session=null,this.resultatCourant=null,this.derniereFiche=null,this.enAttenteRangement=[],this.erreurFile=null,this.navigationArmee=null,this.auRetourDuReseau=()=>{this.file?.rejouer().then(()=>{this.enAttente=this.file.taille(),this.file.viderResultats()})},this.surCodeLu=async e=>{try{const t=await this.connexion.appeler("home_stock/lookup",{code:e.detail.code});this.resultatCourant=t,this.ecran="fiche"}catch{this.derniereFiche={nom:e.detail.code,marque:null,image:null,statut:"Connexion indisponible — réessayez."}}},this.surArticlePret=e=>{const{articleId:t,quantite:i,prixUnitaire:r,mode:n,offDroppedFields:s}=e.detail;if("panier"===n){const e=this.file.ajouter("home_stock/session/add_line",{article_id:t,quantity:i,unit_price:r});return this.enAttente=this.file.taille(),this.file.rejouer().then(()=>{this.enAttente=this.file.taille(),this.file.resultatDe(e)}),this.derniereFiche=function(e,t,i=[]){return e?{nom:e.off?.label??e.article?.label??e.product?.name??e.code,marque:e.off?.brand??e.article?.brand??null,image:e.off?.image??e.article?.image??null,statut:t,ignores:i}:null}(this.resultatCourant,"Ajouté au panier.",s),this.resultatCourant=null,void(this.ecran="scanner")}const o=function(e,t,i,r){return{source:"autonome",id:`autonome-${crypto.randomUUID()}`,article_id:t,quantity:i,unit_price:r,product_name:e?.product?.name??e?.off?.label??e?.article?.label??e?.off?.generic_name??"Article",base_unit:e?.product?.base_unit??"piece",default_location_id:e?.product?.default_location_id??null,default_shelf_life_days:e?.product?.default_shelf_life_days??null,brand:e?.off?.brand??e?.article?.brand??null,image:e?.off?.image??e?.article?.image??null,net_quantity:e?.article?.net_quantity??e?.off?.net_quantity??null}}(this.resultatCourant,t,i,r);this.enAttenteRangement=[...this.enAttenteRangement,o],this.resultatCourant=null,this.ecran="rangement"},this.surLigneAutonomeRangee=e=>{this.enAttenteRangement=this.enAttenteRangement.filter(t=>t.id!==e.detail.id)},this.surRangementTermine=()=>{this.navigationArmee=null,this.ecran="scanner"},this.surFileChangee=()=>{this.enAttente=this.file.taille()}}connectedCallback(){super.connectedCallback(),this.connexion=new me(this.hass),this.file=new ye(window.localStorage,(e,t)=>this.connexion.appeler(e,t),(e,t)=>{this.erreurFile=t}),this.enAttente=this.file.taille(),this.file.rejouer().then(()=>{this.enAttente=this.file.taille(),this.file.viderResultats()}),this.actualiserSession(),this.connexion.abonner(()=>{this.actualiserSession(),this.requestUpdate()}).then(e=>{this.isConnected?this.desabonner=e:e()}),window.addEventListener("online",this.auRetourDuReseau)}disconnectedCallback(){super.disconnectedCallback(),this.desabonner?.(),this.desabonner=void 0,window.removeEventListener("online",this.auRetourDuReseau)}async actualiserSession(){try{this.session=await this.connexion.appeler("home_stock/session/current")}catch{}}get lignesSessionARanger(){return this.session?.session&&"to_store"===this.session.session.state?this.session.lines.filter(e=>null===e.stored_at).map(e=>({...e,source:"session"})):[]}get lignesARanger(){return[...this.lignesSessionARanger,...this.enAttenteRangement]}demanderNavigation(e){"rangement"===this.ecran&&"rangement"!==e&&this.enAttenteRangement.length>0?this.navigationArmee=e:this.ecran=e}confirmerNavigation(){const e=this.navigationArmee;this.navigationArmee=null,e&&(this.ecran=e)}annulerNavigation(){this.navigationArmee=null}rendreNavigation(){if("fiche"===this.ecran)return V;if(this.navigationArmee)return H`
        <div class="confirmation-quitter-rangement">
          <p>
            Des articles rapportés seuls n’ont pas encore été rangés : ils seront perdus si vous quittez
            maintenant.
          </p>
          <button class="confirmer-quitter" @click=${this.confirmerNavigation}>Quitter quand même</button>
          <button class="annuler-quitter" @click=${this.annulerNavigation}>Rester ici</button>
        </div>
      `;const e="shopping"===this.session?.session?.state,t=this.lignesARanger;return H`
      <nav class="navigation">
        ${"scanner"!==this.ecran?H`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("scanner")}>Scanner</button>
        `:V}
        ${e&&"panier"!==this.ecran?H`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("panier")}>
            Panier${this.session.totals.lines?` (${this.session.totals.lines})`:""}
          </button>
        `:V}
        ${t.length>0&&"rangement"!==this.ecran?H`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("rangement")}>
            Ranger (${t.length})
          </button>
        `:V}
        ${"catalogue"!==this.ecran?H`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("catalogue")}>Catalogue</button>
        `:V}
        ${"reglages"!==this.ecran?H`
          <button class="nav-bouton" @click=${()=>this.demanderNavigation("reglages")}>Réglages</button>
        `:V}
      </nav>
    `}rendreErreurFile(){return this.erreurFile?H`
      <p class="erreur-file">
        ${this.erreurFile}
        <button class="fermer-erreur-file" @click=${()=>{this.erreurFile=null}}>OK</button>
      </p>
    `:V}rendreEcran(){return"fiche"===this.ecran&&this.resultatCourant?H`
        <home-stock-fiche .resultat=${this.resultatCourant}
          .mode=${"shopping"===this.session?.session?.state?"panier":"rangement"}
          .connexion=${this.connexion} .file=${this.file} @article-pret=${this.surArticlePret}>
        </home-stock-fiche>`:"panier"===this.ecran&&this.session?H`
        <home-stock-panier .donnees=${this.session} .connexion=${this.connexion}
          .file=${this.file} .enAttente=${this.enAttente} @file-changee=${this.surFileChangee}>
        </home-stock-panier>`:"rangement"===this.ecran?H`
        <home-stock-rangement .lignes=${this.lignesARanger} .connexion=${this.connexion} .file=${this.file}
          .enAttente=${this.enAttente}
          @ligne-autonome-rangee=${this.surLigneAutonomeRangee} @termine=${this.surRangementTermine}
          @file-changee=${this.surFileChangee}>
        </home-stock-rangement>`:"catalogue"===this.ecran?H`
        <home-stock-catalogue .connexion=${this.connexion} .file=${this.file} .enAttente=${this.enAttente}
          @file-changee=${this.surFileChangee}>
        </home-stock-catalogue>`:"reglages"===this.ecran?H`
        <home-stock-reglages .connexion=${this.connexion} .file=${this.file} .enAttente=${this.enAttente}
          @file-changee=${this.surFileChangee}>
        </home-stock-reglages>`:H`
      <home-stock-scanner .session=${this.session?.session?{store:this.session.session.store}:null}
        .derniereFiche=${this.derniereFiche} .enAttente=${this.enAttente} @code-lu=${this.surCodeLu}>
      </home-stock-scanner>`}render(){return H`${this.rendreNavigation()}${this.rendreErreurFile()}${this.rendreEcran()}`}};je.styles=o`
    :host { display: block; height: 100%; background: var(--primary-background-color); }
    .navigation { display: flex; gap: 8px; padding: 8px 12px 0; }
    .nav-bouton {
      flex: 1; min-height: 48px; border-radius: 8px; border: none; font-size: 0.95rem;
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
  `,e([he({attribute:!1})],je.prototype,"hass",void 0),e([he({attribute:!1})],je.prototype,"narrow",void 0),e([pe()],je.prototype,"ecran",void 0),e([pe()],je.prototype,"enAttente",void 0),e([pe()],je.prototype,"session",void 0),e([pe()],je.prototype,"resultatCourant",void 0),e([pe()],je.prototype,"derniereFiche",void 0),e([pe()],je.prototype,"enAttenteRangement",void 0),e([pe()],je.prototype,"erreurFile",void 0),e([pe()],je.prototype,"navigationArmee",void 0),je=e([ce("home-stock-panel")],je);export{je as PanneauGardeManger};
