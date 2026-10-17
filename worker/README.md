# Worker — modulo consulenze

File: `consulenza.js`. Non è ancora pubblicato. Il Worker in produzione è `silent-leaf-495dhobbyimprenditore`.

## Integrazione nel Worker esistente

1. Importa le funzioni in cima al file principale del Worker:

   ```js
   import { richiestaConsulenza, approvaRisposta, riceviRispostaProfessionista, corsPreflight } from './consulenza.js';
   ```

2. Nel `fetch`, prima delle rotte esistenti:

   ```js
   if (request.method === 'OPTIONS' && url.pathname.startsWith('/consulenza')) return corsPreflight();
   if (request.method === 'POST' && url.pathname === '/consulenza') return richiestaConsulenza(request, env);
   if (request.method === 'POST' && url.pathname === '/consulenza/approva') return approvaRisposta(request, env);
   ```

3. Aggiungi l'handler delle email in arrivo, accanto a `fetch`:

   ```js
   async email(message, env, ctx) {
     await riceviRispostaProfessionista(message, env);
   },
   ```

4. Segreti da impostare (non nel codice):
   - `RESEND_API_KEY`: chiave API Resend, solo invio.
   - `ADMIN_EMAIL`: `analizzaste@gmail.com`
   - `FROM_EMAIL`: `richieste@analizzaste.it`

5. Su Cloudflare, Email Routing: l'indirizzo `richieste@analizzaste.it` deve inoltrare al Worker (azione "Send to a Worker").

## Limiti noti

- La risposta del professionista arriva come testo MIME grezzo. Per una lettura pulita serve un parser MIME: lo aggiungiamo dopo il primo test.
- La rotta `/consulenza/approva` richiede che l'admin sia loggato. Il pannello admin non è ancora costruito.
- Il report è allegato come JSON al professionista solo se l'utente l'ha scelto e il report appartiene a lui.
