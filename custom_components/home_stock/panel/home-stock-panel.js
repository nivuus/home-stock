function t(t,e,i,s){var r,n=arguments.length,o=n<3?e:null===s?s=Object.getOwnPropertyDescriptor(e,i):s;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)o=Reflect.decorate(t,e,i,s);else for(var a=t.length-1;a>=0;a--)(r=t[a])&&(o=(n<3?r(o):n>3?r(e,i,o):r(e,i))||o);return n>3&&o&&Object.defineProperty(e,i,o),o}"function"==typeof SuppressedError&&SuppressedError;
/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const e=globalThis,i=e.ShadowRoot&&(void 0===e.ShadyCSS||e.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,s=Symbol(),r=new WeakMap;let n=class{constructor(t,e,i){if(this._$cssResult$=!0,i!==s)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const e=this.t;if(i&&void 0===t){const i=void 0!==e&&1===e.length;i&&(t=r.get(e)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),i&&r.set(e,t))}return t}toString(){return this.cssText}};const o=(t,...e)=>{const i=1===t.length?t[0]:e.reduce((e,i,s)=>e+(t=>{if(!0===t._$cssResult$)return t.cssText;if("number"==typeof t)return t;throw Error("Value passed to 'css' function must be a 'css' function result: "+t+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+t[s+1],t[0]);return new n(i,t,s)},a=i?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e="";for(const i of t.cssRules)e+=i.cssText;return(t=>new n("string"==typeof t?t:t+"",void 0,s))(e)})(t):t,{is:c,defineProperty:l,getOwnPropertyDescriptor:h,getOwnPropertyNames:u,getOwnPropertySymbols:p,getPrototypeOf:d}=Object,f=globalThis,m=f.trustedTypes,$=m?m.emptyScript:"",v=f.reactiveElementPolyfillSupport,_=(t,e)=>t,y={toAttribute(t,e){switch(e){case Boolean:t=t?$:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let i=t;switch(e){case Boolean:i=null!==t;break;case Number:i=null===t?null:Number(t);break;case Object:case Array:try{i=JSON.parse(t)}catch(t){i=null}}return i}},g=(t,e)=>!c(t,e),b={attribute:!0,type:String,converter:y,reflect:!1,useDefault:!1,hasChanged:g};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */Symbol.metadata??=Symbol("metadata"),f.litPropertyMetadata??=new WeakMap;let x=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=b){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){const i=Symbol(),s=this.getPropertyDescriptor(t,i,e);void 0!==s&&l(this.prototype,t,s)}}static getPropertyDescriptor(t,e,i){const{get:s,set:r}=h(this.prototype,t)??{get(){return this[e]},set(t){this[e]=t}};return{get:s,set(e){const n=s?.call(this);r?.call(this,e),this.requestUpdate(t,n,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??b}static _$Ei(){if(this.hasOwnProperty(_("elementProperties")))return;const t=d(this);t.finalize(),void 0!==t.l&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(_("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(_("properties"))){const t=this.properties,e=[...u(t),...p(t)];for(const i of e)this.createProperty(i,t[i])}const t=this[Symbol.metadata];if(null!==t){const e=litPropertyMetadata.get(t);if(void 0!==e)for(const[t,i]of e)this.elementProperties.set(t,i)}this._$Eh=new Map;for(const[t,e]of this.elementProperties){const i=this._$Eu(t,e);void 0!==i&&this._$Eh.set(i,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const i=new Set(t.flat(1/0).reverse());for(const t of i)e.unshift(a(t))}else void 0!==t&&e.push(a(t));return e}static _$Eu(t,e){const i=e.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof t?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),void 0!==this.renderRoot&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,e=this.constructor.elementProperties;for(const i of e.keys())this.hasOwnProperty(i)&&(t.set(i,this[i]),delete this[i]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((t,s)=>{if(i)t.adoptedStyleSheets=s.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(const i of s){const s=document.createElement("style"),r=e.litNonce;void 0!==r&&s.setAttribute("nonce",r),s.textContent=i.cssText,t.appendChild(s)}})(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,i){this._$AK(t,i)}_$ET(t,e){const i=this.constructor.elementProperties.get(t),s=this.constructor._$Eu(t,i);if(void 0!==s&&!0===i.reflect){const r=(void 0!==i.converter?.toAttribute?i.converter:y).toAttribute(e,i.type);this._$Em=t,null==r?this.removeAttribute(s):this.setAttribute(s,r),this._$Em=null}}_$AK(t,e){const i=this.constructor,s=i._$Eh.get(t);if(void 0!==s&&this._$Em!==s){const t=i.getPropertyOptions(s),r="function"==typeof t.converter?{fromAttribute:t.converter}:void 0!==t.converter?.fromAttribute?t.converter:y;this._$Em=s;const n=r.fromAttribute(e,t.type);this[s]=n??this._$Ej?.get(s)??n,this._$Em=null}}requestUpdate(t,e,i,s=!1,r){if(void 0!==t){const n=this.constructor;if(!1===s&&(r=this[t]),i??=n.getPropertyOptions(t),!((i.hasChanged??g)(r,e)||i.useDefault&&i.reflect&&r===this._$Ej?.get(t)&&!this.hasAttribute(n._$Eu(t,i))))return;this.C(t,e,i)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(t,e,{useDefault:i,reflect:s,wrapped:r},n){i&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,n??e??this[t]),!0!==r||void 0!==n)||(this._$AL.has(t)||(this.hasUpdated||i||(e=void 0),this._$AL.set(t,e)),!0===s&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[t,e]of this._$Ep)this[t]=e;this._$Ep=void 0}const t=this.constructor.elementProperties;if(t.size>0)for(const[e,i]of t){const{wrapped:t}=i,s=this[e];!0!==t||this._$AL.has(e)||void 0===s||this.C(e,void 0,i,s)}}let t=!1;const e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(t=>t.hostUpdate?.()),this.update(e)):this._$EM()}catch(e){throw t=!1,this._$EM(),e}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(t){}firstUpdated(t){}};x.elementStyles=[],x.shadowRootOptions={mode:"open"},x[_("elementProperties")]=new Map,x[_("finalized")]=new Map,v?.({ReactiveElement:x}),(f.reactiveElementVersions??=[]).push("2.1.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const A=globalThis,w=t=>t,C=A.trustedTypes,S=C?C.createPolicy("lit-html",{createHTML:t=>t}):void 0,E="$lit$",P=`lit$${Math.random().toFixed(9).slice(2)}$`,k="?"+P,q=`<${k}>`,O=document,N=()=>O.createComment(""),U=t=>null===t||"object"!=typeof t&&"function"!=typeof t,M=Array.isArray,R="[ \t\n\f\r]",H=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,T=/-->/g,z=/>/g,j=RegExp(`>|${R}(?:([^\\s"'>=/]+)(${R}*=${R}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),D=/'/g,I=/"/g,B=/^(?:script|style|textarea|title)$/i,F=(t=>(e,...i)=>({_$litType$:t,strings:e,values:i}))(1),L=Symbol.for("lit-noChange"),V=Symbol.for("lit-nothing"),W=new WeakMap,J=O.createTreeWalker(O,129);function K(t,e){if(!M(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==S?S.createHTML(e):e}const Z=(t,e)=>{const i=t.length-1,s=[];let r,n=2===e?"<svg>":3===e?"<math>":"",o=H;for(let e=0;e<i;e++){const i=t[e];let a,c,l=-1,h=0;for(;h<i.length&&(o.lastIndex=h,c=o.exec(i),null!==c);)h=o.lastIndex,o===H?"!--"===c[1]?o=T:void 0!==c[1]?o=z:void 0!==c[2]?(B.test(c[2])&&(r=RegExp("</"+c[2],"g")),o=j):void 0!==c[3]&&(o=j):o===j?">"===c[0]?(o=r??H,l=-1):void 0===c[1]?l=-2:(l=o.lastIndex-c[2].length,a=c[1],o=void 0===c[3]?j:'"'===c[3]?I:D):o===I||o===D?o=j:o===T||o===z?o=H:(o=j,r=void 0);const u=o===j&&t[e+1].startsWith("/>")?" ":"";n+=o===H?i+q:l>=0?(s.push(a),i.slice(0,l)+E+i.slice(l)+P+u):i+P+(-2===l?e:u)}return[K(t,n+(t[i]||"<?>")+(2===e?"</svg>":3===e?"</math>":"")),s]};class Q{constructor({strings:t,_$litType$:e},i){let s;this.parts=[];let r=0,n=0;const o=t.length-1,a=this.parts,[c,l]=Z(t,e);if(this.el=Q.createElement(c,i),J.currentNode=this.el.content,2===e||3===e){const t=this.el.content.firstChild;t.replaceWith(...t.childNodes)}for(;null!==(s=J.nextNode())&&a.length<o;){if(1===s.nodeType){if(s.hasAttributes())for(const t of s.getAttributeNames())if(t.endsWith(E)){const e=l[n++],i=s.getAttribute(t).split(P),o=/([.?@])?(.*)/.exec(e);a.push({type:1,index:r,name:o[2],strings:i,ctor:"."===o[1]?et:"?"===o[1]?it:"@"===o[1]?st:tt}),s.removeAttribute(t)}else t.startsWith(P)&&(a.push({type:6,index:r}),s.removeAttribute(t));if(B.test(s.tagName)){const t=s.textContent.split(P),e=t.length-1;if(e>0){s.textContent=C?C.emptyScript:"";for(let i=0;i<e;i++)s.append(t[i],N()),J.nextNode(),a.push({type:2,index:++r});s.append(t[e],N())}}}else if(8===s.nodeType)if(s.data===k)a.push({type:2,index:r});else{let t=-1;for(;-1!==(t=s.data.indexOf(P,t+1));)a.push({type:7,index:r}),t+=P.length-1}r++}}static createElement(t,e){const i=O.createElement("template");return i.innerHTML=t,i}}function G(t,e,i=t,s){if(e===L)return e;let r=void 0!==s?i._$Co?.[s]:i._$Cl;const n=U(e)?void 0:e._$litDirective$;return r?.constructor!==n&&(r?._$AO?.(!1),void 0===n?r=void 0:(r=new n(t),r._$AT(t,i,s)),void 0!==s?(i._$Co??=[])[s]=r:i._$Cl=r),void 0!==r&&(e=G(t,r._$AS(t,e.values),r,s)),e}class X{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:e},parts:i}=this._$AD,s=(t?.creationScope??O).importNode(e,!0);J.currentNode=s;let r=J.nextNode(),n=0,o=0,a=i[0];for(;void 0!==a;){if(n===a.index){let e;2===a.type?e=new Y(r,r.nextSibling,this,t):1===a.type?e=new a.ctor(r,a.name,a.strings,this,t):6===a.type&&(e=new rt(r,this,t)),this._$AV.push(e),a=i[++o]}n!==a?.index&&(r=J.nextNode(),n++)}return J.currentNode=O,s}p(t){let e=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}}class Y{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,i,s){this.type=2,this._$AH=V,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=s,this._$Cv=s?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===t?.nodeType&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=G(this,t,e),U(t)?t===V||null==t||""===t?(this._$AH!==V&&this._$AR(),this._$AH=V):t!==this._$AH&&t!==L&&this._(t):void 0!==t._$litType$?this.$(t):void 0!==t.nodeType?this.T(t):(t=>M(t)||"function"==typeof t?.[Symbol.iterator])(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==V&&U(this._$AH)?this._$AA.nextSibling.data=t:this.T(O.createTextNode(t)),this._$AH=t}$(t){const{values:e,_$litType$:i}=t,s="number"==typeof i?this._$AC(t):(void 0===i.el&&(i.el=Q.createElement(K(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===s)this._$AH.p(e);else{const t=new X(s,this),i=t.u(this.options);t.p(e),this.T(i),this._$AH=t}}_$AC(t){let e=W.get(t.strings);return void 0===e&&W.set(t.strings,e=new Q(t)),e}k(t){M(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let i,s=0;for(const r of t)s===e.length?e.push(i=new Y(this.O(N()),this.O(N()),this,this.options)):i=e[s],i._$AI(r),s++;s<e.length&&(this._$AR(i&&i._$AB.nextSibling,s),e.length=s)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){const e=w(t).nextSibling;w(t).remove(),t=e}}setConnected(t){void 0===this._$AM&&(this._$Cv=t,this._$AP?.(t))}}class tt{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,i,s,r){this.type=1,this._$AH=V,this._$AN=void 0,this.element=t,this.name=e,this._$AM=s,this.options=r,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=V}_$AI(t,e=this,i,s){const r=this.strings;let n=!1;if(void 0===r)t=G(this,t,e,0),n=!U(t)||t!==this._$AH&&t!==L,n&&(this._$AH=t);else{const s=t;let o,a;for(t=r[0],o=0;o<r.length-1;o++)a=G(this,s[i+o],e,o),a===L&&(a=this._$AH[o]),n||=!U(a)||a!==this._$AH[o],a===V?t=V:t!==V&&(t+=(a??"")+r[o+1]),this._$AH[o]=a}n&&!s&&this.j(t)}j(t){t===V?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}}class et extends tt{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===V?void 0:t}}class it extends tt{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==V)}}class st extends tt{constructor(t,e,i,s,r){super(t,e,i,s,r),this.type=5}_$AI(t,e=this){if((t=G(this,t,e,0)??V)===L)return;const i=this._$AH,s=t===V&&i!==V||t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive,r=t!==V&&(i===V||s);s&&this.element.removeEventListener(this.name,this,i),r&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}}class rt{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){G(this,t)}}const nt=A.litHtmlPolyfillSupport;nt?.(Q,Y),(A.litHtmlVersions??=[]).push("3.3.3");const ot=globalThis;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */class at extends x{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=((t,e,i)=>{const s=i?.renderBefore??e;let r=s._$litPart$;if(void 0===r){const t=i?.renderBefore??null;s._$litPart$=r=new Y(e.insertBefore(N(),t),t,void 0,i??{})}return r._$AI(t),r})(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return L}}at._$litElement$=!0,at.finalized=!0,ot.litElementHydrateSupport?.({LitElement:at});const ct=ot.litElementPolyfillSupport;ct?.({LitElement:at}),(ot.litElementVersions??=[]).push("4.2.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const lt=t=>(e,i)=>{void 0!==i?i.addInitializer(()=>{customElements.define(t,e)}):customElements.define(t,e)},ht={attribute:!0,type:String,converter:y,reflect:!1,hasChanged:g},ut=(t=ht,e,i)=>{const{kind:s,metadata:r}=i;let n=globalThis.litPropertyMetadata.get(r);if(void 0===n&&globalThis.litPropertyMetadata.set(r,n=new Map),"setter"===s&&((t=Object.create(t)).wrapped=!0),n.set(i.name,t),"accessor"===s){const{name:s}=i;return{set(i){const r=e.get.call(this);e.set.call(this,i),this.requestUpdate(s,r,t,!0,i)},init(e){return void 0!==e&&this.C(s,void 0,t,e),e}}}if("setter"===s){const{name:s}=i;return function(i){const r=this[s];e.call(this,i),this.requestUpdate(s,r,t,!0,i)}}throw Error("Unsupported decorator location: "+s)};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function pt(t){return(e,i)=>"object"==typeof i?ut(t,e,i):((t,e,i)=>{const s=e.hasOwnProperty(i);return e.constructor.createProperty(i,t),s?Object.getOwnPropertyDescriptor(e,i):void 0})(t,e,i)}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function dt(t){return pt({...t,state:!0,attribute:!1})}class ft{constructor(t){this.hass=t}appeler(t,e={}){return this.hass.connection.sendMessagePromise({type:t,...e})}abonner(t){return this.hass.connection.subscribeMessage(t,{type:"home_stock/subscribe"})}}const mt="home_stock.file";class $t{constructor(t,e){this.stockage=t,this.envoyer=e,this.actions=[];try{this.actions=JSON.parse(this.stockage.getItem(mt)??"[]")}catch{this.actions=[]}}ajouter(t,e){const i={...e};return"string"!=typeof i.idempotency_key&&(i.idempotency_key=crypto.randomUUID()),this.actions.push({type:t,charge:i}),this.ecrire(),i.idempotency_key}taille(){return this.actions.length}async rejouer(){for(;this.actions.length;){const t=this.actions[0];try{await this.envoyer(t.type,t.charge)}catch{return}this.actions.shift(),this.ecrire()}}ecrire(){this.stockage.setItem(mt,JSON.stringify(this.actions))}}class vt{constructor(t){this.fenetre=t}disponible(){return Boolean(this.fenetre?.externalApp?.externalBus||this.fenetre?.webkit?.messageHandlers?.externalBus)}lire(){return new Promise(t=>{const e=this.fenetre.externalBus;this.fenetre.externalBus=i=>{const s="string"==typeof i?JSON.parse(i):i;return"bar_code/scan_result"===s.command?(this.envoyer({type:"bar_code/close"}),this.fenetre.externalBus=e,t(String(s.payload.rawValue))):"bar_code/aborted"!==s.command&&"bar_code/close"!==s.command||(this.fenetre.externalBus=e,t(null)),!0},this.envoyer({type:"bar_code/scan",payload:{title:"Scanner un article",description:"Visez le code-barres",alternative_option_label:"Saisir le code"}})})}envoyer(t){const e=JSON.stringify(t);this.fenetre.externalApp?.externalBus?this.fenetre.externalApp.externalBus(e):this.fenetre.webkit.messageHandlers.externalBus.postMessage(t)}}const _t=["ean_13","ean_8","upc_a","upc_e","code_128"];class yt{constructor(t){this.fenetre=t}disponible(){return Boolean(this.fenetre?.BarcodeDetector&&this.fenetre?.navigator?.mediaDevices)}async lire(){const t=new this.fenetre.BarcodeDetector({formats:_t});this.flux=await this.fenetre.navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}});const e=this.fenetre.document.createElement("video");e.srcObject=this.flux,await e.play();try{for(let i=0;i<300;i+=1){const i=await t.detect(e);if(i.length)return String(i[0].rawValue);await new Promise(t=>this.fenetre.requestAnimationFrame(t))}return null}finally{this.arreter()}}arreter(){this.flux?.getTracks().forEach(t=>t.stop()),this.flux=void 0}}class gt{disponible(){return!0}async lire(){return null}}let bt=class extends at{constructor(){super(...arguments),this.fenetre=window,this.derniereFiche=null,this.session=null,this.saisieOuverte=!1,this.codeSaisi="",this.enCours=!1,this.erreur=null}obtenirScanner(){return this.scanner||(this.scanner=function(t){const e=new vt(t);if(e.disponible())return e;const i=new yt(t);return i.disponible()?i:new gt}(this.fenetre??window)),this.scanner}async lancerScan(){const t=this.obtenirScanner();if("ScannerClavier"!==t.constructor.name){this.enCours=!0,this.erreur=null;try{const e=await t.lire();e&&this.emettreCode(e)}catch{this.erreur="La caméra n’a pas pu être utilisée. Essayez la saisie manuelle."}finally{this.enCours=!1}}else this.saisieOuverte=!0}emettreCode(t){this.saisieOuverte=!1,this.codeSaisi="",this.dispatchEvent(new CustomEvent("code-lu",{detail:{code:t},bubbles:!0,composed:!0}))}validerSaisie(){const t=this.codeSaisi.trim();t&&this.emettreCode(t)}render(){return F`
      ${this.session?F`
        <p class="session-banniere">
          Session ouverte${this.session.store?` — ${this.session.store}`:""}
        </p>`:V}

      <button class="bouton-scan" ?disabled=${this.enCours} @click=${this.lancerScan}>
        ${this.enCours?"Scan en cours…":"Scanner un article"}
      </button>

      ${this.erreur?F`<p class="erreur">${this.erreur}</p>`:V}

      ${this.derniereFiche?F`
        <section class="derniere-fiche">
          ${this.derniereFiche.image?F`<img src=${this.derniereFiche.image} alt="" />`:V}
          <p class="derniere-fiche-nom">
            ${this.derniereFiche.nom}${this.derniereFiche.marque?` — ${this.derniereFiche.marque}`:""}
          </p>
          <p class="derniere-fiche-statut">${this.derniereFiche.statut}</p>
        </section>`:V}

      <button class="bouton-saisie" @click=${()=>{this.saisieOuverte=!this.saisieOuverte}}>
        Saisir le code
      </button>

      ${this.saisieOuverte?F`
        <div class="saisie-manuelle">
          <input class="champ-code" inputmode="numeric" placeholder="Code-barres" .value=${this.codeSaisi}
            @input=${t=>{this.codeSaisi=t.target.value}}
            @keydown=${t=>{"Enter"===t.key&&this.validerSaisie()}} />
          <button class="valider-saisie" @click=${this.validerSaisie}>Valider</button>
        </div>`:V}
    `}};bt.styles=o`
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
  `,t([pt({attribute:!1})],bt.prototype,"fenetre",void 0),t([pt({attribute:!1})],bt.prototype,"derniereFiche",void 0),t([pt({attribute:!1})],bt.prototype,"session",void 0),t([dt()],bt.prototype,"saisieOuverte",void 0),t([dt()],bt.prototype,"codeSaisi",void 0),t([dt()],bt.prototype,"enCours",void 0),t([dt()],bt.prototype,"erreur",void 0),bt=t([lt("home-stock-scanner")],bt);const xt={nutriscore:"Nutri-Score",nova:"classification NOVA",ecoscore:"Éco-score",kcal_per_base_unit:"calories",proteins:"protéines",carbohydrates:"glucides",sugars:"sucres",added_sugars:"sucres ajoutés",fat:"matières grasses",saturated_fat:"graisses saturées",fiber:"fibres",salt:"sel"};function At(t,e){const i=Number.parseFloat(t.trim().replace(",","."));if(!Number.isFinite(i))return null;return i/(e&&e>0?e:1)}function wt(t){return t.article?.net_quantity??t.off?.net_quantity??null}let Ct=class extends at{constructor(){super(...arguments),this.mode="rangement",this.productChoisi=null,this.nomNouveauProduit="",this.uniteNouveauProduit="piece",this.prixPaquet="",this.quantitePaquets=1,this.rapportConversion=null,this.enCours=!1,this.creeInfo=null}willUpdate(t){var e,i;t.has("resultat")&&this.resultat&&(this.productChoisi=this.resultat.preselected_product_id,this.nomNouveauProduit=this.resultat.off?.generic_name??"",this.uniteNouveauProduit=this.resultat.off?.net_unit??"piece",this.prixPaquet=(e=this.resultat.price?.price_per_base_unit,i=wt(this.resultat),null==e?"":(e*(i&&i>0?i:1)).toFixed(2).replace(".",",")),this.quantitePaquets=1,this.rapportConversion=null,this.creeInfo=null)}get peutValider(){return!(!this.resultat||this.enCours)&&(!!this.resultat.known||!!this.connexion&&("new"===this.productChoisi?this.nomNouveauProduit.trim().length>0:"number"==typeof this.productChoisi))}async valider(){if(this.peutValider){this.enCours=!0;try{let t;if(this.resultat.known)t=this.resultat.article.id;else{const e={code:this.resultat.code};this.resultat.off_raw&&(e.off=this.resultat.off_raw),this.resultat.off_source&&(e.off_source=this.resultat.off_source),"new"===this.productChoisi?e.new_product={name:this.nomNouveauProduit.trim(),base_unit:this.uniteNouveauProduit}:e.product_id=this.productChoisi;const i=await this.connexion.appeler("home_stock/article/create",e);t=i.article_id,this.creeInfo=i}const e=wt(this.resultat),i=e&&e>0?e:1;this.dispatchEvent(new CustomEvent("article-pret",{detail:{articleId:t,quantite:i*this.quantitePaquets,prixUnitaire:At(this.prixPaquet,e),mode:this.mode},bubbles:!0,composed:!0}))}finally{this.enCours=!1}}}async voirEffetConversion(){const t=this.resultat.conversion_offer;t&&this.connexion&&(this.rapportConversion=await this.connexion.appeler("home_stock/product/convert_unit",{product_id:t.product_id,to_unit:t.to_unit,reference_quantity:t.reference_quantity,dry_run:!0}))}async appliquerConversion(){const t=this.resultat.conversion_offer;t&&this.connexion&&this.rapportConversion&&(this.rapportConversion=await this.connexion.appeler("home_stock/product/convert_unit",{product_id:t.product_id,to_unit:t.to_unit,reference_quantity:t.reference_quantity,dry_run:!1}))}rendreRattachement(){return this.resultat.known?V:F`
      <section class="rattachement">
        ${this.resultat.candidates.map(t=>F`
          <label class="candidat">
            <input type="radio" name="produit" .value=${String(t.product_id)}
              .checked=${this.productChoisi===t.product_id}
              @change=${()=>{this.productChoisi=t.product_id}} />
            <span>${t.name}</span>
          </label>
        `)}
        <label class="candidat nouveau">
          <input type="radio" name="produit" value="new"
            .checked=${"new"===this.productChoisi}
            @change=${()=>{this.productChoisi="new"}} />
          <span>Nouveau produit</span>
        </label>
        ${"new"===this.productChoisi?F`
          <div class="nouveau-produit">
            <input class="nom-nouveau" placeholder="Nom du produit" .value=${this.nomNouveauProduit}
              @input=${t=>{this.nomNouveauProduit=t.target.value}} />
            <select class="unite-nouveau" .value=${this.uniteNouveauProduit}
              @change=${t=>{this.uniteNouveauProduit=t.target.value}}>
              <option value="g">grammes</option>
              <option value="ml">millilitres</option>
              <option value="piece">à la pièce</option>
            </select>
          </div>`:V}
      </section>
    `}rendreConversion(){const t=this.resultat.conversion_offer;return t?F`
      <section class="conversion-offre">
        <p>Passer de pièce à ${t.to_unit} — 1 unité = ${t.reference_quantity} ${t.to_unit}</p>
        ${this.rapportConversion?F`
          <p class="rapport-conversion">
            ${this.rapportConversion.articles} article(s),
            ${this.rapportConversion.batches} lot(s),
            ${this.rapportConversion.movements} mouvement(s) concernés.
          </p>
          ${this.rapportConversion.applied?F`<p class="conversion-appliquee">Conversion appliquée.</p>`:F`<button class="appliquer-conversion" @click=${this.appliquerConversion}>
                Appliquer la conversion
              </button>`}
        `:F`<button class="voir-effet" @click=${this.voirEffetConversion}>
            Voir l'effet du changement d'unité
          </button>`}
      </section>
    `:V}render(){if(!this.resultat)return V;const t=this.resultat,e=t.off?.label??t.article?.label??t.product?.name??"Article",i=t.off?.brand??t.article?.brand??null,s=wt(t),r=(n=t,n.product?.base_unit??n.off?.net_unit??"");var n;const o=t.off?.image??t.article?.image??null,a=t.off?.nutriscore??t.article?.nutriscore??null,c=function(t){const e=t.off?.nutrition_per_100?.kcal;if(null!=e)return e;const i=t.article?.kcal_per_base_unit,s=t.product?.base_unit;return null==i||"g"!==s&&"ml"!==s?null:100*i}(t),l=At(this.prixPaquet,wt(t));return F`
      <section class="entete">
        ${o?F`<img class="image" src=${o} alt="" />`:V}
        <h2 class="nom">${e}</h2>
        ${i?F`<p class="marque">${i}</p>`:V}
        ${s?F`<p class="poids">${s} ${r}</p>`:V}
        ${a?F`<p class="nutriscore">Nutri-Score ${a.toUpperCase()}</p>`:V}
        ${null!=c?F`<p class="kcal">${Math.round(c)} kcal / 100 g</p>`:V}
      </section>

      ${this.rendreRattachement()}

      <section class="prix">
        <p class="prix-provenance">${h=t.price,h&&null!=h.price_per_base_unit&&h.source?"store"===h.source?h.store?`dernier prix ${h.store}`:"dernier prix en magasin":"open_prices"===h.source?"Open Prices":"dernier prix connu":"Aucun prix connu"}</p>
        <label class="prix-label">
          Prix payé (paquet)
          <input class="prix-champ" inputmode="decimal" .value=${this.prixPaquet}
            @input=${t=>{this.prixPaquet=t.target.value}} />
        </label>
        ${null!=l?F`
          <p class="prix-detail">soit ${l.toFixed(4).replace(".",",")} €/${r||"unité"}</p>
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

      ${this.creeInfo&&this.creeInfo.off_dropped_fields.length?F`
        <p class="ignores">
          Ignoré par Open Food Facts :
          ${this.creeInfo.off_dropped_fields.map(t=>xt[t]??t).join(", ")}
        </p>`:V}

      <button class="action-principale" ?disabled=${!this.peutValider} @click=${this.valider}>
        ${"panier"===this.mode?"Au panier":"Ranger"}
      </button>
    `;var h}};function St(t,e){if(!t)return null;return{nom:t.off?.label??t.article?.label??t.product?.name??t.code,marque:t.off?.brand??t.article?.brand??null,image:t.off?.image??t.article?.image??null,statut:e}}Ct.styles=o`
    :host { display: block; padding: 12px; box-sizing: border-box; color: var(--primary-text-color); }
    .image { max-width: 100%; max-height: 160px; display: block; margin: 0 auto 8px; border-radius: 8px; }
    .nom { margin: 0; font-size: 1.2rem; }
    .marque, .poids, .nutriscore, .kcal { margin: 2px 0; color: var(--secondary-text-color); }
    .candidat { display: flex; align-items: center; gap: 8px; min-height: 48px; }
    .candidat input { width: 22px; height: 22px; }
    .nom-nouveau, .prix-champ, .unite-nouveau {
      min-height: 48px; font-size: 1rem; padding: 4px 8px; box-sizing: border-box; width: 100%;
    }
    .prix { margin: 12px 0; }
    .prix-provenance { color: var(--secondary-text-color); margin: 0 0 4px; }
    .prix-detail { color: var(--secondary-text-color); font-size: 0.85rem; }
    .quantite { display: flex; align-items: center; gap: 12px; margin: 12px 0; }
    .quantite button {
      min-width: 62px; min-height: 62px; font-size: 1.5rem; border-radius: 8px; border: none;
      background: var(--primary-color); color: var(--text-primary-color, #fff);
    }
    .valeur-quantite { min-width: 32px; text-align: center; font-size: 1.2rem; }
    .conversion-offre { margin: 12px 0; padding: 8px; border-radius: 8px; background: var(--secondary-background-color); }
    .ignores { color: var(--secondary-text-color); font-size: 0.85rem; }
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
  `,t([pt({attribute:!1})],Ct.prototype,"resultat",void 0),t([pt({attribute:!1})],Ct.prototype,"mode",void 0),t([pt({attribute:!1})],Ct.prototype,"connexion",void 0),t([dt()],Ct.prototype,"productChoisi",void 0),t([dt()],Ct.prototype,"nomNouveauProduit",void 0),t([dt()],Ct.prototype,"uniteNouveauProduit",void 0),t([dt()],Ct.prototype,"prixPaquet",void 0),t([dt()],Ct.prototype,"quantitePaquets",void 0),t([dt()],Ct.prototype,"rapportConversion",void 0),t([dt()],Ct.prototype,"enCours",void 0),t([dt()],Ct.prototype,"creeInfo",void 0),Ct=t([lt("home-stock-fiche")],Ct);let Et=class extends at{constructor(){super(...arguments),this.narrow=!1,this.ecran="scanner",this.enAttente=0,this.session=null,this.resultatCourant=null,this.derniereFiche=null,this.auRetourDuReseau=()=>{this.file?.rejouer().then(()=>{this.enAttente=this.file.taille()})},this.surCodeLu=async t=>{try{const e=await this.connexion.appeler("home_stock/lookup",{code:t.detail.code});this.resultatCourant=e,this.ecran="fiche"}catch{this.derniereFiche={nom:t.detail.code,marque:null,image:null,statut:"Connexion indisponible — réessayez."}}},this.surArticlePret=async t=>{const{articleId:e,quantite:i,prixUnitaire:s,mode:r}=t.detail;if("panier"===r)try{await this.connexion.appeler("home_stock/session/add_line",{article_id:e,quantity:i,unit_price:s??void 0,idempotency_key:crypto.randomUUID()}),this.derniereFiche=St(this.resultatCourant,"Ajouté au panier.")}catch{this.derniereFiche=St(this.resultatCourant,"Non envoyé — hors ligne.")}else this.derniereFiche=St(this.resultatCourant,"Article créé — reste à ranger.");this.resultatCourant=null,this.ecran="scanner"}}connectedCallback(){super.connectedCallback(),this.connexion=new ft(this.hass),this.file=new $t(window.localStorage,(t,e)=>this.connexion.appeler(t,e)),this.enAttente=this.file.taille(),this.file.rejouer().then(()=>{this.enAttente=this.file.taille()}),this.actualiserSession(),this.connexion.abonner(()=>{this.actualiserSession(),this.requestUpdate()}).then(t=>{this.isConnected?this.desabonner=t:t()}),window.addEventListener("online",this.auRetourDuReseau)}disconnectedCallback(){super.disconnectedCallback(),this.desabonner?.(),this.desabonner=void 0,window.removeEventListener("online",this.auRetourDuReseau)}async actualiserSession(){try{const t=await this.connexion.appeler("home_stock/session/current");this.session=t?{store:t.store}:null}catch{}}render(){return"scanner"===this.ecran?F`
        <home-stock-scanner .session=${this.session} .derniereFiche=${this.derniereFiche}
          @code-lu=${this.surCodeLu}>
        </home-stock-scanner>`:"fiche"===this.ecran&&this.resultatCourant?F`
        <home-stock-fiche .resultat=${this.resultatCourant}
          .mode=${this.session?"panier":"rangement"} .connexion=${this.connexion}
          @article-pret=${this.surArticlePret}>
        </home-stock-fiche>`:F`<div class="ecran">${this.ecran}</div>`}};Et.styles=o`
    :host { display: block; height: 100%; background: var(--primary-background-color); }
  `,t([pt({attribute:!1})],Et.prototype,"hass",void 0),t([pt({attribute:!1})],Et.prototype,"narrow",void 0),t([dt()],Et.prototype,"ecran",void 0),t([dt()],Et.prototype,"enAttente",void 0),t([dt()],Et.prototype,"session",void 0),t([dt()],Et.prototype,"resultatCourant",void 0),t([dt()],Et.prototype,"derniereFiche",void 0),Et=t([lt("home-stock-panel")],Et);export{Et as PanneauGardeManger};
