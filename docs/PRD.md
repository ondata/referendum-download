# Project Title: Referendum Download CLI

## Brief Description

- CLI Python che, data una pagina referendum su eligendo (elezionistorico.interno.gov.it), scarica tutti i dati via API in formato JSONLines, in modo idempotente.

## Problem Statement

- I dati dei referendum su eligendo sono consultabili solo via web, non esiste un modo semplice per scaricarli in bulk in formato machine-readable.

## Objectives

- Scaricare tutti i dati di un referendum dato l'URL della pagina su eligendo
- Salvare i dati in formato JSONLines (machine-readable)
- Operazione idempotente (rieseguibile senza duplicati/problemi)
- Documentare le API sottostanti di eligendo prima di scrivere codice

## Target Audience / Users

- Data journalist, civic hacker, ricercatori che lavorano con dati elettorali italiani

## Key Features / Components

- CLI Python con argomento URL della pagina referendum
- Reverse engineering e documentazione delle API di eligendo
- Download strutturato dei dati a tutti i livelli geografici (nazionale, regionale, provinciale, comunale)
- Output in formato JSONLines
- Idempotenza: se rieseguito, non riscarica dati già presenti

## Success Criteria

- Dati scaricati corrispondono a quelli visibili sul sito eligendo
- Il file JSONLines è valido e parsabile
- Riesecuzione dello script non produce duplicati né errori

## Constraints / Limitations

- Dipendenza dalle API non documentate di eligendo (possono cambiare senza preavviso)
- Solo referendum (tipo tpel=F), non altre tipologie elettorali (per ora)

## Timeline

- Completamento: 2026-03-14
