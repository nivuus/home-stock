function e(e,t,i,s){var r,n=arguments.length,o=n<3?t:null===s?s=Object.getOwnPropertyDescriptor(t,i):s;if("object"==typeof Reflect&&"function"==typeof Reflect.decorate)o=Reflect.decorate(e,t,i,s);else for(var a=e.length-1;a>=0;a--)(r=e[a])&&(o=(n<3?r(o):n>3?r(t,i,o):r(t,i))||o);return n>3&&o&&Object.defineProperty(t,i,o),o}"function"==typeof SuppressedError&&SuppressedError;
/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const t=globalThis,i=t.ShadowRoot&&(void 0===t.ShadyCSS||t.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,s=Symbol(),r=new WeakMap;let n=class{constructor(e,t,i){if(this._$cssResult$=!0,i!==s)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o;const t=this.t;if(i&&void 0===e){const i=void 0!==t&&1===t.length;i&&(e=r.get(t)),void 0===e&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),i&&r.set(t,e))}return e}toString(){return this.cssText}};const o=(e,...t)=>{const i=1===e.length?e[0]:t.reduce((t,i,s)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if("number"==typeof e)return e;throw Error("Value passed to 'css' function must be a 'css' function result: "+e+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+e[s+1],e[0]);return new n(i,e,s)},a=i?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t="";for(const i of e.cssRules)t+=i.cssText;return(e=>new n("string"==typeof e?e:e+"",void 0,s))(t)})(e):e,{is:c,defineProperty:l,getOwnPropertyDescriptor:u,getOwnPropertyNames:h,getOwnPropertySymbols:p,getPrototypeOf:d}=Object,f=globalThis,m=f.trustedTypes,v=m?m.emptyScript:"",$=f.reactiveElementPolyfillSupport,g=(e,t)=>e,_={toAttribute(e,t){switch(t){case Boolean:e=e?v:null;break;case Object:case Array:e=null==e?e:JSON.stringify(e)}return e},fromAttribute(e,t){let i=e;switch(t){case Boolean:i=null!==e;break;case Number:i=null===e?null:Number(e);break;case Object:case Array:try{i=JSON.parse(e)}catch(e){i=null}}return i}},y=(e,t)=>!c(e,t),b={attribute:!0,type:String,converter:_,reflect:!1,useDefault:!1,hasChanged:y};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */Symbol.metadata??=Symbol("metadata"),f.litPropertyMetadata??=new WeakMap;let x=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=b){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){const i=Symbol(),s=this.getPropertyDescriptor(e,i,t);void 0!==s&&l(this.prototype,e,s)}}static getPropertyDescriptor(e,t,i){const{get:s,set:r}=u(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:s,set(t){const n=s?.call(this);r?.call(this,t),this.requestUpdate(e,n,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??b}static _$Ei(){if(this.hasOwnProperty(g("elementProperties")))return;const e=d(this);e.finalize(),void 0!==e.l&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(g("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(g("properties"))){const e=this.properties,t=[...h(e),...p(e)];for(const i of t)this.createProperty(i,e[i])}const e=this[Symbol.metadata];if(null!==e){const t=litPropertyMetadata.get(e);if(void 0!==t)for(const[e,i]of t)this.elementProperties.set(e,i)}this._$Eh=new Map;for(const[e,t]of this.elementProperties){const i=this._$Eu(e,t);void 0!==i&&this._$Eh.set(i,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){const t=[];if(Array.isArray(e)){const i=new Set(e.flat(1/0).reverse());for(const e of i)t.unshift(a(e))}else void 0!==e&&t.push(a(e));return t}static _$Eu(e,t){const i=t.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof e?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),void 0!==this.renderRoot&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){const e=new Map,t=this.constructor.elementProperties;for(const i of t.keys())this.hasOwnProperty(i)&&(e.set(i,this[i]),delete this[i]);e.size>0&&(this._$Ep=e)}createRenderRoot(){const e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((e,s)=>{if(i)e.adoptedStyleSheets=s.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(const i of s){const s=document.createElement("style"),r=t.litNonce;void 0!==r&&s.setAttribute("nonce",r),s.textContent=i.cssText,e.appendChild(s)}})(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,i){this._$AK(e,i)}_$ET(e,t){const i=this.constructor.elementProperties.get(e),s=this.constructor._$Eu(e,i);if(void 0!==s&&!0===i.reflect){const r=(void 0!==i.converter?.toAttribute?i.converter:_).toAttribute(t,i.type);this._$Em=e,null==r?this.removeAttribute(s):this.setAttribute(s,r),this._$Em=null}}_$AK(e,t){const i=this.constructor,s=i._$Eh.get(e);if(void 0!==s&&this._$Em!==s){const e=i.getPropertyOptions(s),r="function"==typeof e.converter?{fromAttribute:e.converter}:void 0!==e.converter?.fromAttribute?e.converter:_;this._$Em=s;const n=r.fromAttribute(t,e.type);this[s]=n??this._$Ej?.get(s)??n,this._$Em=null}}requestUpdate(e,t,i,s=!1,r){if(void 0!==e){const n=this.constructor;if(!1===s&&(r=this[e]),i??=n.getPropertyOptions(e),!((i.hasChanged??y)(r,t)||i.useDefault&&i.reflect&&r===this._$Ej?.get(e)&&!this.hasAttribute(n._$Eu(e,i))))return;this.C(e,t,i)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:i,reflect:s,wrapped:r},n){i&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,n??t??this[e]),!0!==r||void 0!==n)||(this._$AL.has(e)||(this.hasUpdated||i||(t=void 0),this._$AL.set(e,t)),!0===s&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}const e=this.scheduleUpdate();return null!=e&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}const e=this.constructor.elementProperties;if(e.size>0)for(const[t,i]of e){const{wrapped:e}=i,s=this[t];!0!==e||this._$AL.has(t)||void 0===s||this.C(t,void 0,i,s)}}let e=!1;const t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};x.elementStyles=[],x.shadowRootOptions={mode:"open"},x[g("elementProperties")]=new Map,x[g("finalized")]=new Map,$?.({ReactiveElement:x}),(f.reactiveElementVersions??=[]).push("2.1.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const A=globalThis,C=e=>e,w=A.trustedTypes,S=w?w.createPolicy("lit-html",{createHTML:e=>e}):void 0,E="$lit$",P=`lit$${Math.random().toFixed(9).slice(2)}$`,k="?"+P,q=`<${k}>`,U=document,O=()=>U.createComment(""),N=e=>null===e||"object"!=typeof e&&"function"!=typeof e,R=Array.isArray,M="[ \t\n\f\r]",F=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,T=/-->/g,z=/>/g,H=RegExp(`>|${M}(?:([^\\s"'>=/]+)(${M}*=${M}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),j=/'/g,B=/"/g,D=/^(?:script|style|textarea|title)$/i,I=(e=>(t,...i)=>({_$litType$:e,strings:t,values:i}))(1),L=Symbol.for("lit-noChange"),V=Symbol.for("lit-nothing"),W=new WeakMap,J=U.createTreeWalker(U,129);function K(e,t){if(!R(e)||!e.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==S?S.createHTML(t):t}const Q=(e,t)=>{const i=e.length-1,s=[];let r,n=2===t?"<svg>":3===t?"<math>":"",o=F;for(let t=0;t<i;t++){const i=e[t];let a,c,l=-1,u=0;for(;u<i.length&&(o.lastIndex=u,c=o.exec(i),null!==c);)u=o.lastIndex,o===F?"!--"===c[1]?o=T:void 0!==c[1]?o=z:void 0!==c[2]?(D.test(c[2])&&(r=RegExp("</"+c[2],"g")),o=H):void 0!==c[3]&&(o=H):o===H?">"===c[0]?(o=r??F,l=-1):void 0===c[1]?l=-2:(l=o.lastIndex-c[2].length,a=c[1],o=void 0===c[3]?H:'"'===c[3]?B:j):o===B||o===j?o=H:o===T||o===z?o=F:(o=H,r=void 0);const h=o===H&&e[t+1].startsWith("/>")?" ":"";n+=o===F?i+q:l>=0?(s.push(a),i.slice(0,l)+E+i.slice(l)+P+h):i+P+(-2===l?t:h)}return[K(e,n+(e[i]||"<?>")+(2===t?"</svg>":3===t?"</math>":"")),s]};class Z{constructor({strings:e,_$litType$:t},i){let s;this.parts=[];let r=0,n=0;const o=e.length-1,a=this.parts,[c,l]=Q(e,t);if(this.el=Z.createElement(c,i),J.currentNode=this.el.content,2===t||3===t){const e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;null!==(s=J.nextNode())&&a.length<o;){if(1===s.nodeType){if(s.hasAttributes())for(const e of s.getAttributeNames())if(e.endsWith(E)){const t=l[n++],i=s.getAttribute(e).split(P),o=/([.?@])?(.*)/.exec(t);a.push({type:1,index:r,name:o[2],strings:i,ctor:"."===o[1]?te:"?"===o[1]?ie:"@"===o[1]?se:ee}),s.removeAttribute(e)}else e.startsWith(P)&&(a.push({type:6,index:r}),s.removeAttribute(e));if(D.test(s.tagName)){const e=s.textContent.split(P),t=e.length-1;if(t>0){s.textContent=w?w.emptyScript:"";for(let i=0;i<t;i++)s.append(e[i],O()),J.nextNode(),a.push({type:2,index:++r});s.append(e[t],O())}}}else if(8===s.nodeType)if(s.data===k)a.push({type:2,index:r});else{let e=-1;for(;-1!==(e=s.data.indexOf(P,e+1));)a.push({type:7,index:r}),e+=P.length-1}r++}}static createElement(e,t){const i=U.createElement("template");return i.innerHTML=e,i}}function G(e,t,i=e,s){if(t===L)return t;let r=void 0!==s?i._$Co?.[s]:i._$Cl;const n=N(t)?void 0:t._$litDirective$;return r?.constructor!==n&&(r?._$AO?.(!1),void 0===n?r=void 0:(r=new n(e),r._$AT(e,i,s)),void 0!==s?(i._$Co??=[])[s]=r:i._$Cl=r),void 0!==r&&(t=G(e,r._$AS(e,t.values),r,s)),t}class X{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){const{el:{content:t},parts:i}=this._$AD,s=(e?.creationScope??U).importNode(t,!0);J.currentNode=s;let r=J.nextNode(),n=0,o=0,a=i[0];for(;void 0!==a;){if(n===a.index){let t;2===a.type?t=new Y(r,r.nextSibling,this,e):1===a.type?t=new a.ctor(r,a.name,a.strings,this,e):6===a.type&&(t=new re(r,this,e)),this._$AV.push(t),a=i[++o]}n!==a?.index&&(r=J.nextNode(),n++)}return J.currentNode=U,s}p(e){let t=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(e,i,t),t+=i.strings.length-2):i._$AI(e[t])),t++}}class Y{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,i,s){this.type=2,this._$AH=V,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=i,this.options=s,this._$Cv=s?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode;const t=this._$AM;return void 0!==t&&11===e?.nodeType&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=G(this,e,t),N(e)?e===V||null==e||""===e?(this._$AH!==V&&this._$AR(),this._$AH=V):e!==this._$AH&&e!==L&&this._(e):void 0!==e._$litType$?this.$(e):void 0!==e.nodeType?this.T(e):(e=>R(e)||"function"==typeof e?.[Symbol.iterator])(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==V&&N(this._$AH)?this._$AA.nextSibling.data=e:this.T(U.createTextNode(e)),this._$AH=e}$(e){const{values:t,_$litType$:i}=e,s="number"==typeof i?this._$AC(e):(void 0===i.el&&(i.el=Z.createElement(K(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===s)this._$AH.p(t);else{const e=new X(s,this),i=e.u(this.options);e.p(t),this.T(i),this._$AH=e}}_$AC(e){let t=W.get(e.strings);return void 0===t&&W.set(e.strings,t=new Z(e)),t}k(e){R(this._$AH)||(this._$AH=[],this._$AR());const t=this._$AH;let i,s=0;for(const r of e)s===t.length?t.push(i=new Y(this.O(O()),this.O(O()),this,this.options)):i=t[s],i._$AI(r),s++;s<t.length&&(this._$AR(i&&i._$AB.nextSibling,s),t.length=s)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){const t=C(e).nextSibling;C(e).remove(),e=t}}setConnected(e){void 0===this._$AM&&(this._$Cv=e,this._$AP?.(e))}}class ee{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,i,s,r){this.type=1,this._$AH=V,this._$AN=void 0,this.element=e,this.name=t,this._$AM=s,this.options=r,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=V}_$AI(e,t=this,i,s){const r=this.strings;let n=!1;if(void 0===r)e=G(this,e,t,0),n=!N(e)||e!==this._$AH&&e!==L,n&&(this._$AH=e);else{const s=e;let o,a;for(e=r[0],o=0;o<r.length-1;o++)a=G(this,s[i+o],t,o),a===L&&(a=this._$AH[o]),n||=!N(a)||a!==this._$AH[o],a===V?e=V:e!==V&&(e+=(a??"")+r[o+1]),this._$AH[o]=a}n&&!s&&this.j(e)}j(e){e===V?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}}class te extends ee{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===V?void 0:e}}class ie extends ee{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==V)}}class se extends ee{constructor(e,t,i,s,r){super(e,t,i,s,r),this.type=5}_$AI(e,t=this){if((e=G(this,e,t,0)??V)===L)return;const i=this._$AH,s=e===V&&i!==V||e.capture!==i.capture||e.once!==i.once||e.passive!==i.passive,r=e!==V&&(i===V||s);s&&this.element.removeEventListener(this.name,this,i),r&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}}class re{constructor(e,t,i){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(e){G(this,e)}}const ne=A.litHtmlPolyfillSupport;ne?.(Z,Y),(A.litHtmlVersions??=[]).push("3.3.3");const oe=globalThis;
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */class ae extends x{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){const t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=((e,t,i)=>{const s=i?.renderBefore??t;let r=s._$litPart$;if(void 0===r){const e=i?.renderBefore??null;s._$litPart$=r=new Y(t.insertBefore(O(),e),e,void 0,i??{})}return r._$AI(e),r})(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return L}}ae._$litElement$=!0,ae.finalized=!0,oe.litElementHydrateSupport?.({LitElement:ae});const ce=oe.litElementPolyfillSupport;ce?.({LitElement:ae}),(oe.litElementVersions??=[]).push("4.2.2");
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */
const le=e=>(t,i)=>{void 0!==i?i.addInitializer(()=>{customElements.define(e,t)}):customElements.define(e,t)},ue={attribute:!0,type:String,converter:_,reflect:!1,hasChanged:y},he=(e=ue,t,i)=>{const{kind:s,metadata:r}=i;let n=globalThis.litPropertyMetadata.get(r);if(void 0===n&&globalThis.litPropertyMetadata.set(r,n=new Map),"setter"===s&&((e=Object.create(e)).wrapped=!0),n.set(i.name,e),"accessor"===s){const{name:s}=i;return{set(i){const r=t.get.call(this);t.set.call(this,i),this.requestUpdate(s,r,e,!0,i)},init(t){return void 0!==t&&this.C(s,void 0,e,t),t}}}if("setter"===s){const{name:s}=i;return function(i){const r=this[s];t.call(this,i),this.requestUpdate(s,r,e,!0,i)}}throw Error("Unsupported decorator location: "+s)};
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function pe(e){return(t,i)=>"object"==typeof i?he(e,t,i):((e,t,i)=>{const s=t.hasOwnProperty(i);return t.constructor.createProperty(i,e),s?Object.getOwnPropertyDescriptor(t,i):void 0})(e,t,i)}
/**
 * @license
 * Copyright 2017 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */function de(e){return pe({...e,state:!0,attribute:!1})}class fe{constructor(e){this.hass=e}appeler(e,t={}){return this.hass.connection.sendMessagePromise({type:e,...t})}abonner(e){return this.hass.connection.subscribeMessage(e,{type:"home_stock/subscribe"})}}const me="home_stock.file";class ve{constructor(e,t){this.stockage=e,this.envoyer=t,this.actions=[];try{this.actions=JSON.parse(this.stockage.getItem(me)??"[]")}catch{this.actions=[]}}ajouter(e,t){const i={...t};return"string"!=typeof i.idempotency_key&&(i.idempotency_key=crypto.randomUUID()),this.actions.push({type:e,charge:i}),this.ecrire(),i.idempotency_key}taille(){return this.actions.length}async rejouer(){for(;this.actions.length;){const e=this.actions[0];try{await this.envoyer(e.type,e.charge)}catch{return}this.actions.shift(),this.ecrire()}}ecrire(){this.stockage.setItem(me,JSON.stringify(this.actions))}}class $e{constructor(e){this.fenetre=e}disponible(){return Boolean(this.fenetre?.externalApp?.externalBus||this.fenetre?.webkit?.messageHandlers?.externalBus)}lire(){return new Promise(e=>{const t=this.fenetre.externalBus;let i=!1;const s=s=>{i||(i=!0,clearTimeout(r),this.fenetre.externalBus=t,e(s))},r=setTimeout(()=>s(null),6e4);this.fenetre.externalBus=e=>{const t="string"==typeof e?JSON.parse(e):e;return"bar_code/scan_result"===t.command?(this.envoyer({type:"bar_code/close"}),s(String(t.payload.rawValue))):"bar_code/aborted"!==t.command&&"bar_code/close"!==t.command||s(null),!0},this.envoyer({type:"bar_code/scan",payload:{title:"Scanner un article",description:"Visez le code-barres",alternative_option_label:"Saisir le code"}})})}envoyer(e){const t=JSON.stringify(e);this.fenetre.externalApp?.externalBus?this.fenetre.externalApp.externalBus(t):this.fenetre.webkit.messageHandlers.externalBus.postMessage(e)}}const ge=["ean_13","ean_8","upc_a","upc_e","code_128"];class _e{constructor(e){this.fenetre=e}disponible(){return Boolean(this.fenetre?.BarcodeDetector&&this.fenetre?.navigator?.mediaDevices)}async lire(){try{const e=new this.fenetre.BarcodeDetector({formats:ge});this.flux=await this.fenetre.navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}});const t=this.fenetre.document.createElement("video");t.srcObject=this.flux,t.setAttribute("playsinline","true"),t.setAttribute("muted","true"),t.style.cssText="position:fixed;inset:0;width:100%;height:100%;object-fit:cover;z-index:2147483647;background:#000;",this.fenetre.document.body.appendChild(t),this.video=t,await t.play();for(let i=0;i<300;i+=1){const i=await e.detect(t);if(i.length)return String(i[0].rawValue);await new Promise(e=>this.fenetre.requestAnimationFrame(e))}return null}finally{this.arreter()}}arreter(){this.flux?.getTracks().forEach(e=>e.stop()),this.flux=void 0,this.video?.remove(),this.video=void 0}}class ye{disponible(){return!0}async lire(){return null}}const be={label:"nom",brand:"marque",net_quantity:"poids net",image:"image",kcal_per_base_unit:"calories",proteins:"protéines",carbohydrates:"glucides",sugars:"sucres",added_sugars:"sucres ajoutés",fat:"matières grasses",saturated_fat:"graisses saturées",fiber:"fibres",salt:"sel",nutriscore:"Nutri-Score",nova:"classification NOVA",ecoscore:"Éco-score",allergens:"allergènes",traces:"traces",additives:"additifs",off_labels:"labels",off_raw:"réponse Open Food Facts"};function xe(e,t,i){const s=Number.parseFloat(e.trim().replace(",","."));return Number.isFinite(s)?"piece"===t?s:"g"===t||"ml"===t?null===i||i<=0?null:s/i:null:null}function Ae(e){return e.known?e.article?.net_quantity??null:e.off?.net_quantity??null}function Ce(e){return e&&"object"==typeof e&&"message"in e&&"string"==typeof e.message?e.message:"Une erreur est survenue."}let we=class extends ae{constructor(){super(...arguments),this.mode="rangement",this.productChoisi=null,this.nomNouveauProduit="",this.uniteNouveauProduit="piece",this.prixSaisi=null,this.poidsPaquet="",this.quantitePaquets=1,this.produitsBaseUnit={},this.rapportConversion=null,this.erreurConversion=null,this.erreurAction=null,this.erreurUnites=null,this.enCours=!1}willUpdate(e){if(e.has("resultat")&&this.resultat){this.productChoisi=this.resultat.preselected_product_id,this.nomNouveauProduit=this.resultat.off?.generic_name??"",this.uniteNouveauProduit=this.resultat.off?.net_unit??"piece";const e=Ae(this.resultat);this.poidsPaquet=null!==e?String(e):"",this.prixSaisi=null,this.quantitePaquets=1,this.rapportConversion=null,this.erreurConversion=null,this.erreurAction=null,this.erreurUnites=null,this.produitsBaseUnit={}}}updated(e){e.has("resultat")&&this.resultat&&!this.resultat.known&&this.resultat.candidates.length&&this.connexion&&this.chargerUnitesProduits()}async chargerUnitesProduits(){this.erreurUnites=null;try{const e=await this.connexion.appeler("home_stock/products/list"),t={};for(const i of e.products)t[i.id]=i.base_unit;this.produitsBaseUnit=t}catch{this.erreurUnites="Impossible de récupérer les informations du produit. Vérifiez la connexion."}}uniteConnue(){return this.resultat.known?this.resultat.product?.base_unit??null:"new"===this.productChoisi?this.uniteNouveauProduit:"number"==typeof this.productChoisi?this.produitsBaseUnit[this.productChoisi]??null:null}get poidsEffectif(){return function(e){const t=Number.parseFloat(e.trim().replace(",","."));return Number.isFinite(t)&&t>0?t:null}(this.poidsPaquet)}get valeurPrix(){if(null!==this.prixSaisi)return this.prixSaisi;const e=this.uniteConnue(),t="piece"===e?null:this.poidsEffectif;return function(e,t,i){return null==e?"":"piece"===t?e.toFixed(2).replace(".",","):"g"===t||"ml"===t?null===i||i<=0?"":(e*i).toFixed(2).replace(".",","):""}(this.resultat.price?.price_per_base_unit,e,t)}get raisonBlocage(){if(!this.resultat)return null;if(!this.resultat.known){if(!this.connexion)return"Connexion indisponible.";if(null===this.productChoisi)return"Choisissez un produit.";if("new"===this.productChoisi&&!this.nomNouveauProduit.trim())return"Donnez un nom au nouveau produit."}const e=this.uniteConnue();return null===e?this.erreurUnites??"Chargement des informations du produit…":"g"!==e&&"ml"!==e||null!==this.poidsEffectif?null:"Indiquez le poids du paquet pour calculer le prix."}get peutValider(){return!this.enCours&&null===this.raisonBlocage}enregistrerPoidsCorrige(e,t){const i={article_id:e,fields:{net_quantity:t}};this.file?this.file.ajouter("home_stock/article/update",i):this.connexion&&this.connexion.appeler("home_stock/article/update",i).catch(()=>{})}async valider(){if(this.peutValider){this.enCours=!0,this.erreurAction=null;try{const e=this.uniteConnue(),t="piece"===e?null:this.poidsEffectif,i=null===Ae(this.resultat);let s,r=[];if(this.resultat.known)s=this.resultat.article.id,null!==t&&i&&this.enregistrerPoidsCorrige(s,t);else{const e={code:this.resultat.code};this.resultat.off_raw&&(e.off=this.resultat.off_raw),this.resultat.off_source&&(e.off_source=this.resultat.off_source),"new"===this.productChoisi?e.new_product={name:this.nomNouveauProduit.trim(),base_unit:this.uniteNouveauProduit}:e.product_id=this.productChoisi,null!==t&&i&&(e.fields={net_quantity:t});const n=await this.connexion.appeler("home_stock/article/create",e);s=n.article_id,r=n.off_dropped_fields??[]}const n={articleId:s,quantite:"piece"===e?this.quantitePaquets:t*this.quantitePaquets,prixUnitaire:xe(this.valeurPrix,e,t),mode:this.mode,offDroppedFields:r};this.dispatchEvent(new CustomEvent("article-pret",{detail:n,bubbles:!0,composed:!0}))}catch(e){this.erreurAction=Ce(e)}finally{this.enCours=!1}}}async voirEffetConversion(){const e=this.resultat.conversion_offer;if(e&&this.connexion){this.erreurConversion=null;try{this.rapportConversion=await this.connexion.appeler("home_stock/product/convert_unit",{product_id:e.product_id,to_unit:e.to_unit,reference_quantity:e.reference_quantity,dry_run:!0})}catch(e){this.erreurConversion=Ce(e)}}}async appliquerConversion(){const e=this.resultat.conversion_offer;if(e&&this.connexion&&this.rapportConversion){this.erreurConversion=null;try{this.rapportConversion=await this.connexion.appeler("home_stock/product/convert_unit",{product_id:e.product_id,to_unit:e.to_unit,reference_quantity:e.reference_quantity,dry_run:!1})}catch(e){this.erreurConversion=Ce(e)}}}rendreRattachement(){return this.resultat.known?V:I`
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
          </div>`:V}
        ${this.erreurUnites?I`
          <p class="erreur-unite">${this.erreurUnites}</p>
          <button class="reessayer-unite" @click=${()=>{this.chargerUnitesProduits()}}>
            Réessayer
          </button>`:V}
      </section>
    `}rendreAlerteOff(){const e=this.resultat;return e.known||e.off?V:e.throttled?I`<p class="alerte-off">Open Food Facts limite les requêtes en ce moment — réessayez
        dans un instant plutôt que de créer un doublon.</p>`:e.timed_out?I`<p class="alerte-off">Open Food Facts n'a pas répondu à temps — le produit existe
        peut-être déjà là-bas, réessayez avant de créer un doublon.</p>`:V}rendreConversion(){const e=this.resultat.conversion_offer;return e?I`
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
        ${this.erreurConversion?I`<p class="erreur-conversion">${this.erreurConversion}</p>`:V}
      </section>
    `:V}render(){if(!this.resultat)return V;const e=this.resultat,t=e.off?.label??e.article?.label??e.product?.name??"Article",i=e.off?.brand??e.article?.brand??null,s=e.article?.net_quantity??e.off?.net_quantity??null,r=e.product?.base_unit??e.off?.net_unit??"",n=e.off?.image??e.article?.image??null,o=e.off?.nutriscore??e.article?.nutriscore??null,a=function(e){const t=e.off?.nutrition_per_100?.kcal;if(null!=t)return t;const i=e.article?.kcal_per_base_unit,s=e.product?.base_unit;return null==i||"g"!==s&&"ml"!==s?null:100*i}(e),c=this.uniteConnue(),l="piece"===c?null:this.poidsEffectif,u="g"===c||"ml"===c?xe(this.valeurPrix,c,l):null,h=null!=u?1e3*u:null,p="ml"===c?"L":"kg";return I`
      <section class="entete">
        ${n?I`<img class="image" src=${n} alt="" />`:V}
        <h2 class="nom">${t}</h2>
        ${i?I`<p class="marque">${i}</p>`:V}
        ${s?I`<p class="poids">${s} ${r}</p>`:V}
        ${o?I`<p class="nutriscore">Nutri-Score ${o.toUpperCase()}</p>`:V}
        ${null!=a?I`<p class="kcal">${Math.round(a)} kcal / 100 g</p>`:V}
      </section>

      ${this.rendreAlerteOff()}
      ${this.rendreRattachement()}

      <section class="prix">
        <p class="prix-provenance">${d=e.price,d&&null!=d.price_per_base_unit&&d.source?"store"===d.source?d.store?`dernier prix ${d.store}`:"dernier prix en magasin":"open_prices"===d.source?"Open Prices":"dernier prix connu":"Aucun prix connu"}</p>
        ${"g"!==c&&"ml"!==c||null!==Ae(e)?V:I`
          <label class="poids-label">
            Poids du paquet
            <input class="poids-champ" inputmode="decimal" placeholder="ex. 500" .value=${this.poidsPaquet}
              @input=${e=>{this.poidsPaquet=e.target.value}} />
            <span>${"ml"===c?"ml":"g"}</span>
          </label>`}
        <label class="prix-label">
          ${"piece"===c?"Prix payé (€ / unité)":"Prix payé (paquet)"}
          <input class="prix-champ" inputmode="decimal" .value=${this.valeurPrix}
            @input=${e=>{this.prixSaisi=e.target.value}} />
        </label>
        ${null!=h?I`
          <p class="prix-detail">soit ${h.toFixed(2).replace(".",",")} €/${p}</p>
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

      ${this.raisonBlocage?I`<p class="motif-blocage">${this.raisonBlocage}</p>`:V}
      ${this.erreurAction?I`<p class="erreur-action">${this.erreurAction}</p>`:V}

      <button class="action-principale" ?disabled=${!this.peutValider} @click=${this.valider}>
        ${"panier"===this.mode?"Au panier":"Ranger"}
      </button>
    `;var d}};we.styles=o`
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
  `,e([pe({attribute:!1})],we.prototype,"resultat",void 0),e([pe({attribute:!1})],we.prototype,"mode",void 0),e([pe({attribute:!1})],we.prototype,"connexion",void 0),e([pe({attribute:!1})],we.prototype,"file",void 0),e([de()],we.prototype,"productChoisi",void 0),e([de()],we.prototype,"nomNouveauProduit",void 0),e([de()],we.prototype,"uniteNouveauProduit",void 0),e([de()],we.prototype,"prixSaisi",void 0),e([de()],we.prototype,"poidsPaquet",void 0),e([de()],we.prototype,"quantitePaquets",void 0),e([de()],we.prototype,"produitsBaseUnit",void 0),e([de()],we.prototype,"rapportConversion",void 0),e([de()],we.prototype,"erreurConversion",void 0),e([de()],we.prototype,"erreurAction",void 0),e([de()],we.prototype,"erreurUnites",void 0),e([de()],we.prototype,"enCours",void 0),we=e([le("home-stock-fiche")],we);let Se=class extends ae{constructor(){super(...arguments),this.fenetre=window,this.derniereFiche=null,this.session=null,this.enAttente=0,this.saisieOuverte=!1,this.codeSaisi="",this.enCours=!1,this.erreur=null}obtenirScanner(){return this.scanner||(this.scanner=function(e){const t=new $e(e);if(t.disponible())return t;const i=new _e(e);return i.disponible()?i:new ye}(this.fenetre??window)),this.scanner}async lancerScan(){const e=this.obtenirScanner();if("ScannerClavier"!==e.constructor.name){this.enCours=!0,this.erreur=null;try{const t=await e.lire();t&&this.emettreCode(t)}catch{this.erreur="La caméra n’a pas pu être utilisée. Essayez la saisie manuelle."}finally{this.enCours=!1}}else this.saisieOuverte=!0}emettreCode(e){this.saisieOuverte=!1,this.codeSaisi="",this.dispatchEvent(new CustomEvent("code-lu",{detail:{code:e},bubbles:!0,composed:!0}))}validerSaisie(){const e=this.codeSaisi.trim();e&&this.emettreCode(e)}render(){return I`
      ${this.session?I`
        <p class="session-banniere">
          Session ouverte${this.session.store?` — ${this.session.store}`:""}
        </p>`:V}

      <button class="bouton-scan" ?disabled=${this.enCours} @click=${this.lancerScan}>
        ${this.enCours?"Scan en cours…":"Scanner un article"}
      </button>

      ${this.erreur?I`<p class="erreur">${this.erreur}</p>`:V}

      ${this.derniereFiche?I`
        <section class="derniere-fiche">
          ${this.derniereFiche.image?I`<img src=${this.derniereFiche.image} alt="" />`:V}
          <p class="derniere-fiche-nom">
            ${this.derniereFiche.nom}${this.derniereFiche.marque?` — ${this.derniereFiche.marque}`:""}
          </p>
          <p class="derniere-fiche-statut">${this.derniereFiche.statut}</p>
          ${void 0!==this.derniereFiche.quantite?I`
            <p class="derniere-fiche-quantite">
              Quantité : ${this.derniereFiche.quantite}${null!=this.derniereFiche.prixTotal?` — ${this.derniereFiche.prixTotal.toFixed(2).replace(".",",")} €`:""}
            </p>`:V}
          ${this.derniereFiche.ignores?.length?I`
            <p class="derniere-fiche-ignores">
              Ignoré par Open Food Facts : ${e=this.derniereFiche.ignores,e.map(e=>be[e]??e).join(", ")}
            </p>`:V}
        </section>`:V}

      ${this.enAttente>0?I`
        <p class="en-attente">${this.enAttente} envoi${this.enAttente>1?"s":""} en attente de réseau</p>
      `:V}

      <button class="bouton-saisie" @click=${()=>{this.saisieOuverte=!this.saisieOuverte}}>
        Saisir le code
      </button>

      ${this.saisieOuverte?I`
        <div class="saisie-manuelle">
          <input class="champ-code" inputmode="numeric" placeholder="Code-barres" .value=${this.codeSaisi}
            @input=${e=>{this.codeSaisi=e.target.value}}
            @keydown=${e=>{"Enter"===e.key&&this.validerSaisie()}} />
          <button class="valider-saisie" @click=${this.validerSaisie}>Valider</button>
        </div>`:V}
    `;var e}};function Ee(e,t,i=[],s,r){if(!e)return null;return{nom:e.off?.label??e.article?.label??e.product?.name??e.code,marque:e.off?.brand??e.article?.brand??null,image:e.off?.image??e.article?.image??null,statut:t,ignores:i,quantite:s,prixTotal:void 0!==s&&null!=r?r*s:null}}Se.styles=o`
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
  `,e([pe({attribute:!1})],Se.prototype,"fenetre",void 0),e([pe({attribute:!1})],Se.prototype,"derniereFiche",void 0),e([pe({attribute:!1})],Se.prototype,"session",void 0),e([pe({attribute:!1})],Se.prototype,"enAttente",void 0),e([de()],Se.prototype,"saisieOuverte",void 0),e([de()],Se.prototype,"codeSaisi",void 0),e([de()],Se.prototype,"enCours",void 0),e([de()],Se.prototype,"erreur",void 0),Se=e([le("home-stock-scanner")],Se);let Pe=class extends ae{constructor(){super(...arguments),this.narrow=!1,this.ecran="scanner",this.enAttente=0,this.session=null,this.resultatCourant=null,this.derniereFiche=null,this.auRetourDuReseau=()=>{this.file?.rejouer().then(()=>{this.enAttente=this.file.taille()})},this.surCodeLu=async e=>{try{const t=await this.connexion.appeler("home_stock/lookup",{code:e.detail.code});this.resultatCourant=t,this.ecran="fiche"}catch{this.derniereFiche={nom:e.detail.code,marque:null,image:null,statut:"Connexion indisponible — réessayez."}}},this.surArticlePret=e=>{const{articleId:t,quantite:i,prixUnitaire:s,mode:r,offDroppedFields:n}=e.detail;"panier"===r?(this.file.ajouter("home_stock/session/add_line",{article_id:t,quantity:i,unit_price:s}),this.enAttente=this.file.taille(),this.file.rejouer().then(()=>{this.enAttente=this.file.taille()}),this.derniereFiche=Ee(this.resultatCourant,"Ajouté au panier.",n)):this.derniereFiche=Ee(this.resultatCourant,"Article créé — reste à choisir l’emplacement.",n,i,s),this.resultatCourant=null,this.ecran="scanner"}}connectedCallback(){super.connectedCallback(),this.connexion=new fe(this.hass),this.file=new ve(window.localStorage,(e,t)=>this.connexion.appeler(e,t)),this.enAttente=this.file.taille(),this.file.rejouer().then(()=>{this.enAttente=this.file.taille()}),this.actualiserSession(),this.connexion.abonner(()=>{this.actualiserSession(),this.requestUpdate()}).then(e=>{this.isConnected?this.desabonner=e:e()}),window.addEventListener("online",this.auRetourDuReseau)}disconnectedCallback(){super.disconnectedCallback(),this.desabonner?.(),this.desabonner=void 0,window.removeEventListener("online",this.auRetourDuReseau)}async actualiserSession(){try{const e=await this.connexion.appeler("home_stock/session/current");this.session=e?{store:e.store}:null}catch{}}render(){return"scanner"===this.ecran?I`
        <home-stock-scanner .session=${this.session} .derniereFiche=${this.derniereFiche}
          .enAttente=${this.enAttente} @code-lu=${this.surCodeLu}>
        </home-stock-scanner>`:"fiche"===this.ecran&&this.resultatCourant?I`
        <home-stock-fiche .resultat=${this.resultatCourant}
          .mode=${this.session?"panier":"rangement"} .connexion=${this.connexion}
          .file=${this.file} @article-pret=${this.surArticlePret}>
        </home-stock-fiche>`:I`<div class="ecran">${this.ecran}</div>`}};Pe.styles=o`
    :host { display: block; height: 100%; background: var(--primary-background-color); }
  `,e([pe({attribute:!1})],Pe.prototype,"hass",void 0),e([pe({attribute:!1})],Pe.prototype,"narrow",void 0),e([de()],Pe.prototype,"ecran",void 0),e([de()],Pe.prototype,"enAttente",void 0),e([de()],Pe.prototype,"session",void 0),e([de()],Pe.prototype,"resultatCourant",void 0),e([de()],Pe.prototype,"derniereFiche",void 0),Pe=e([le("home-stock-panel")],Pe);export{Pe as PanneauGardeManger};
